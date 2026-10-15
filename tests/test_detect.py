from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from docmorph.core.detect import detect
from docmorph.core.errors import UnsupportedFormat
from docmorph.core.models import Format, PdfKind
from tests.conftest import make_zip


def test_digital_pdf(two_column_pdf: Path) -> None:
    d = detect(two_column_pdf)
    assert d.format == Format.PDF
    assert d.pdf_kind == PdfKind.DIGITAL
    assert d.pages == 1


def test_scanned_pdf(scanned_pdf: Path) -> None:
    d = detect(scanned_pdf)
    assert d.pdf_kind == PdfKind.SCANNED
    assert d.scanned_pages == 1


def test_encrypted_pdf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "secret.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "secret")
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    with pytest.raises(UnsupportedFormat, match="mot de passe"):
        detect(path)


def test_images(png_with_alpha: Path, jpg_file: Path) -> None:
    assert detect(png_with_alpha).format == Format.PNG
    assert detect(jpg_file).format == Format.JPG


def test_docx_detected_from_content_even_with_wrong_extension(docx_file: Path) -> None:
    renamed = docx_file.with_suffix(".bin")
    docx_file.rename(renamed)
    assert detect(renamed).format == Format.DOCX


def test_ooxml_and_odf_containers(tmp_path: Path) -> None:
    xlsx = make_zip(tmp_path / "a.zip", {"[Content_Types].xml": "<x/>", "xl/workbook.xml": "<w/>"})
    pptx = make_zip(tmp_path / "b.zip", {"[Content_Types].xml": "<x/>", "ppt/presentation.xml": "<p/>"})
    ods = make_zip(
        tmp_path / "c.zip",
        {"mimetype": "application/vnd.oasis.opendocument.spreadsheet", "content.xml": "<c/>"},
        stored_first="mimetype",
    )
    assert detect(xlsx).format == Format.XLSX
    assert detect(pptx).format == Format.PPTX
    assert detect(ods).format == Format.ODS


def test_ole_legacy_formats(tmp_path: Path) -> None:
    header = bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 504
    doc = tmp_path / "old.doc"
    doc.write_bytes(header + "WordDocument".encode("utf-16-le") + b"\x00" * 64)
    xls = tmp_path / "old.xls"
    xls.write_bytes(header + "Workbook".encode("utf-16-le") + b"\x00" * 64)
    # libmagic may also identify these; either way the format must be right.
    assert detect(doc).format == Format.DOC
    assert detect(xls).format == Format.XLS


def test_text_and_rtf(txt_utf8: Path, txt_cp1252: Path, rtf_file: Path) -> None:
    assert detect(txt_utf8).format == Format.TXT
    assert detect(txt_cp1252, "ancien.txt").format == Format.TXT
    assert detect(rtf_file).format == Format.RTF


def test_unknown_binary_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "blob.dat"
    path.write_bytes(bytes(range(256)) * 10)
    with pytest.raises(UnsupportedFormat):
        detect(path)
