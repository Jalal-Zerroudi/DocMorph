"""Format detection from file content (libmagic + container inspection), extension last."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pymupdf

from docmorph.core.errors import UnsupportedFormat
from docmorph.core.models import Detection, Format, PdfKind

try:
    import magic
except ImportError:  # libmagic missing: content sniffing below still covers every supported format
    magic = None

_ODF_MIMETYPES = {
    "application/vnd.oasis.opendocument.text": Format.ODT,
    "application/vnd.oasis.opendocument.spreadsheet": Format.ODS,
    "application/vnd.oasis.opendocument.presentation": Format.ODP,
}
_OOXML_PARTS = {"word/": Format.DOCX, "xl/": Format.XLSX, "ppt/": Format.PPTX}
_OLE_STREAMS = {
    "WordDocument": Format.DOC,
    "Workbook": Format.XLS,
    "Book": Format.XLS,
    "PowerPoint Document": Format.PPT,
}
_MAGIC_MIMES = {
    "application/msword": Format.DOC,
    "application/vnd.ms-excel": Format.XLS,
    "application/vnd.ms-powerpoint": Format.PPT,
}
_EXTENSIONS = {f.extension: f for f in Format} | {".jpeg": Format.JPG}

_OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
_TEXT_PROBE_BYTES = 64 * 1024

# A page counts as scanned when it has (almost) no extractable text and images cover most of it.
_MIN_TEXT_CHARS = 25
_MIN_IMAGE_COVERAGE = 0.5
_MAX_PAGES_SAMPLED = 200


def detect(path: Path, original_name: str | None = None) -> Detection:
    fmt, mime = _sniff(path)
    if fmt is None:
        fmt = _EXTENSIONS.get(Path(original_name or path.name).suffix.lower())
        if fmt is None or (fmt == Format.TXT and not _looks_like_text(path)):
            raise UnsupportedFormat(
                "Format de fichier non pris en charge.",
                detail=f"Type détecté : {mime or 'inconnu'}",
            )
    if fmt == Format.PDF:
        return _detect_pdf(path, mime)
    return Detection(format=fmt, mime=mime)


def _sniff(path: Path) -> tuple[Format | None, str | None]:
    mime = _magic_mime(path)
    with path.open("rb") as fh:
        head = fh.read(8)

    if head.startswith(b"%PDF-"):
        return Format.PDF, mime
    if head.startswith(b"\x89PNG"):
        return Format.PNG, mime
    if head.startswith(b"\xff\xd8\xff"):
        return Format.JPG, mime
    if head.startswith(b"{\\rtf"):
        return Format.RTF, mime
    if head.startswith(b"PK"):
        return _sniff_zip(path), mime
    if head.startswith(_OLE_SIGNATURE):
        return _sniff_ole(path, mime), mime
    if (mime or "").startswith("text/") or (mime is None and _looks_like_text(path)):
        return Format.TXT, mime
    return None, mime


def _magic_mime(path: Path) -> str | None:
    if magic is None:
        return None
    try:
        return magic.from_file(str(path), mime=True)
    except Exception:
        return None


def _sniff_zip(path: Path) -> Format | None:
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if "mimetype" in names:
                return _ODF_MIMETYPES.get(zf.read("mimetype").decode("ascii", "ignore").strip())
            if "[Content_Types].xml" in names:
                for prefix, fmt in _OOXML_PARTS.items():
                    if any(n.startswith(prefix) for n in names):
                        return fmt
    except zipfile.BadZipFile:
        return None
    return None


def _sniff_ole(path: Path, mime: str | None) -> Format | None:
    if mime in _MAGIC_MIMES:
        return _MAGIC_MIMES[mime]
    data = path.read_bytes()
    for stream, fmt in _OLE_STREAMS.items():
        if stream.encode("utf-16-le") in data:
            return fmt
    return None


def _looks_like_text(path: Path) -> bool:
    with path.open("rb") as fh:
        sample = fh.read(_TEXT_PROBE_BYTES)
    if not sample:
        return False
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    if b"\x00" in sample:
        return False
    # Accepts UTF-8 as well as legacy 8-bit encodings (cp1252, latin-1): only control bytes disqualify.
    controls = sum(1 for b in sample if b < 0x09 or 0x0E <= b < 0x20 or b == 0x7F)
    return controls / len(sample) < 0.01


def _detect_pdf(path: Path, mime: str | None) -> Detection:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise UnsupportedFormat("PDF illisible ou corrompu.", detail=str(exc)) from exc
    with doc:
        if doc.needs_pass:
            raise UnsupportedFormat("PDF protégé par mot de passe : impossible de le convertir.")
        sampled = min(doc.page_count, _MAX_PAGES_SAMPLED)
        scanned = sum(1 for i in range(sampled) if _is_scanned_page(doc[i]))
        pages = doc.page_count
    # Mixed documents (at least half of the pages are images) go through OCR.
    kind = PdfKind.SCANNED if sampled and scanned * 2 >= sampled else PdfKind.DIGITAL
    return Detection(format=Format.PDF, pdf_kind=kind, mime=mime, pages=pages, scanned_pages=scanned)


def _is_scanned_page(page: pymupdf.Page) -> bool:
    if len(page.get_text("text").strip()) >= _MIN_TEXT_CHARS:
        return False
    page_area = abs(page.rect)
    if not page_area:
        return False
    covered = 0.0
    for info in page.get_image_info():
        covered += abs(pymupdf.Rect(info["bbox"]) & page.rect)
    return covered / page_area >= _MIN_IMAGE_COVERAGE
