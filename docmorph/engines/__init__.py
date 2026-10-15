from __future__ import annotations

from docmorph.core.engine import Engine
from docmorph.engines.images import ImageToPdfEngine
from docmorph.engines.libreoffice import LibreOfficeEngine
from docmorph.engines.ocr import OcrTextEngine
from docmorph.engines.pdf_layout import PdfLayoutEngine
from docmorph.engines.pdf_structure import PdfStructureEngine
from docmorph.engines.pdf_text import PdfTextEngine


def default_engines() -> list[Engine]:
    return [
        LibreOfficeEngine(),
        PdfLayoutEngine(),
        PdfStructureEngine(),
        OcrTextEngine(),
        ImageToPdfEngine(),
        PdfTextEngine(),
    ]
