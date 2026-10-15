"""Structure mode: Docling (layout, tables, formulas as LaTeX, optional Tesseract OCR) -> Markdown
-> Pandoc -> DOCX with native, editable Word equations."""

from __future__ import annotations

import logging
import shutil
import tempfile
import threading
from functools import cache
from pathlib import Path

from docmorph.config import settings
from docmorph.core.engine import Engine
from docmorph.core.errors import ConversionFailed
from docmorph.core.models import Format, Mode, PdfKind, Resource, Route
from docmorph.core.text import is_mostly_arabic
from docmorph.engines import _proc
from docmorph.engines.ocr import missing_tesseract_langs

try:
    import torch
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import ConversionStatus, InputFormat
    from docling.datamodel.pipeline_options import OcrMode, PdfPipelineOptions, TesseractCliOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import ImageRefMode
except ImportError:  # optional dependency (pip install docmorph[structure])
    DocumentConverter = None

log = logging.getLogger(__name__)

_PANDOC_TIMEOUT_S = 300
_DOCUMENT_TIMEOUT_S = 1800.0
_IMAGES_SCALE = 2.0


class PdfStructureEngine(Engine):
    name = "docling"
    label = "Docling + Pandoc (structure)"
    resource = Resource.GPU
    routes = (
        Route(Format.PDF, Format.DOCX, Mode.STRUCTURE, PdfKind.DIGITAL),
        Route(Format.PDF, Format.DOCX, Mode.STRUCTURE, PdfKind.SCANNED),
    )

    def __init__(self) -> None:
        self._converters: dict[tuple[str, bool], DocumentConverter] = {}
        self._lock = threading.Lock()

    def availability(self) -> str | None:
        if DocumentConverter is None:
            return "Docling n'est pas installé (pip install docmorph[structure])."
        if shutil.which("pandoc") is None:
            return "Pandoc n'est pas installé (paquet pandoc)."
        return None

    def route_availability(self, route: Route) -> str | None:
        return missing_tesseract_langs() if route.pdf_kind == PdfKind.SCANNED else None

    def convert(self, src: Path, dst: Path, route: Route) -> None:
        ocr = route.pdf_kind == PdfKind.SCANNED
        with tempfile.TemporaryDirectory(prefix="docmorph-docling-") as tmp:
            markdown = Path(tmp) / "document.md"
            self._to_markdown(src, markdown, ocr)
            _markdown_to_docx(markdown, dst)

    def _to_markdown(self, src: Path, markdown: Path, ocr: bool) -> None:
        device = preferred_device()
        try:
            result = self._run_docling(src, device, ocr)
        except _GpuOutOfMemory:
            log.warning("GPU out of memory, retrying %s on CPU", src.name)
            torch.cuda.empty_cache()
            result = self._run_docling(src, "cpu", ocr)
        result.document.save_as_markdown(markdown, image_mode=ImageRefMode.REFERENCED)

    def _run_docling(self, src: Path, device: str, ocr: bool):
        try:
            result = self._converter(device, ocr).convert(src, raises_on_error=False)
        except Exception as exc:
            if device == "cuda" and _is_out_of_memory(str(exc)):
                raise _GpuOutOfMemory from exc
            raise ConversionFailed("Docling a échoué.", detail=str(exc)) from exc
        if result.status in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
            return result
        errors = "; ".join(e.error_message for e in result.errors)
        if device == "cuda" and _is_out_of_memory(errors):
            raise _GpuOutOfMemory
        raise ConversionFailed("Docling n'a pas pu analyser ce PDF.", detail=errors or str(result.status))

    def _converter(self, device: str, ocr: bool) -> DocumentConverter:
        key = (device, ocr)
        with self._lock:
            if key not in self._converters:
                self._converters[key] = _build_converter(device, ocr)
            return self._converters[key]


def _build_converter(device: str, ocr: bool) -> DocumentConverter:
    options = PdfPipelineOptions(
        artifacts_path=settings.docling_artifacts,
        do_ocr=ocr,
        do_table_structure=True,
        do_formula_enrichment=True,
        generate_picture_images=True,
        images_scale=_IMAGES_SCALE,
        document_timeout=_DOCUMENT_TIMEOUT_S,
        accelerator_options=AcceleratorOptions(
            device=AcceleratorDevice.CUDA if device == "cuda" else AcceleratorDevice.CPU
        ),
    )
    if ocr:
        options.ocr_options = TesseractCliOcrOptions(lang=list(settings.ocr_langs), mode=OcrMode.FULL_PAGE)
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})


def _markdown_to_docx(markdown: Path, dst: Path) -> None:
    cmd = [
        "pandoc", str(markdown),
        "--from", "markdown+tex_math_dollars+pipe_tables",
        "--to", "docx",
        "--resource-path", str(markdown.parent),
        "--output", str(dst),
    ]
    if is_mostly_arabic(markdown.read_text(encoding="utf-8")):
        cmd += ["--metadata", "dir=rtl", "--metadata", "lang=ar"]
    _proc.run(cmd, _PANDOC_TIMEOUT_S, "Pandoc")
    if not dst.is_file() or dst.stat().st_size == 0:
        raise ConversionFailed("Pandoc n'a produit aucun fichier.")


@cache
def preferred_device() -> str:
    """'cuda' when a GPU is usable by this PyTorch build, else 'cpu'. DOCMORPH_DEVICE overrides."""
    if settings.device in ("cuda", "cpu"):
        return settings.device
    if DocumentConverter is None or not torch.cuda.is_available():
        return "cpu"
    try:
        # Fails with "no kernel image" when the build no longer supports this GPU architecture.
        (torch.ones(8, device="cuda") * 2).sum().item()
    except Exception as exc:
        log.warning("CUDA present but unusable (%s); using CPU", exc)
        return "cpu"
    return "cuda"


class _GpuOutOfMemory(Exception):
    pass


def _is_out_of_memory(message: str) -> bool:
    return "out of memory" in message.lower()
