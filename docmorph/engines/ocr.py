from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from functools import cache
from pathlib import Path

from docmorph.config import settings
from docmorph.core.engine import Engine
from docmorph.core.models import Format, PdfKind, Resource, Route
from docmorph.engines import _proc
from docmorph.engines.pdf_text import extract_text

_TIMEOUT_S = 1800


class OcrTextEngine(Engine):
    """Scanned PDF -> text: OCRmyPDF adds a Tesseract text layer, PyMuPDF then extracts it."""

    name = "ocrmypdf"
    label = "OCRmyPDF + Tesseract"
    resource = Resource.CPU
    routes = (Route(Format.PDF, Format.TXT, pdf_kind=PdfKind.SCANNED),)

    def availability(self) -> str | None:
        if importlib.util.find_spec("ocrmypdf") is None:
            return "Le paquet Python ocrmypdf n'est pas installé."
        if shutil.which("gs") is None:
            return "Ghostscript n'est pas installé (paquet ghostscript)."
        return missing_tesseract_langs()

    def convert(self, src: Path, dst: Path, route: Route) -> None:
        with tempfile.TemporaryDirectory(prefix="docmorph-ocr-") as tmp:
            searchable = Path(tmp) / "ocr.pdf"
            cmd = [
                sys.executable, "-m", "ocrmypdf",
                "--language", "+".join(settings.ocr_langs),
                "--skip-text",
                "--rotate-pages",
                "--deskew",
                "--output-type", "pdf",
                "--optimize", "0",
                "--jobs", str(os.cpu_count() or 2),
                "--quiet",
                str(src), str(searchable),
            ]
            _proc.run(cmd, _TIMEOUT_S, "OCRmyPDF")
            dst.write_text(extract_text(searchable), encoding="utf-8")


@cache
def missing_tesseract_langs() -> str | None:
    """None when Tesseract and every configured language pack are installed, else the reason."""
    tesseract = shutil.which("tesseract")
    if tesseract is None:
        return "Tesseract n'est pas installé (paquet tesseract-ocr)."
    out = subprocess.run([tesseract, "--list-langs"], capture_output=True, text=True).stdout
    installed = set(out.split())
    missing = [lang for lang in settings.ocr_langs if lang not in installed]
    if missing:
        packages = " ".join(f"tesseract-ocr-{lang}" for lang in missing)
        return f"Langues OCR manquantes : {', '.join(missing)} (paquets {packages})."
    return None
