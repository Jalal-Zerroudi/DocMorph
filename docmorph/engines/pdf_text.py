from __future__ import annotations

import math
from pathlib import Path

import pymupdf

from docmorph.core.engine import Engine
from docmorph.core.models import Format, PdfKind, Resource, Route
from docmorph.core.text import is_mostly_arabic

_COLUMN_TOLERANCE = 0.02


class PdfTextEngine(Engine):
    name = "pymupdf-text"
    label = "PyMuPDF (texte)"
    resource = Resource.CPU
    routes = (Route(Format.PDF, Format.TXT, pdf_kind=PdfKind.DIGITAL),)

    def availability(self) -> str | None:
        return None

    def convert(self, src: Path, dst: Path, route: Route) -> None:
        dst.write_text(extract_text(src), encoding="utf-8")


def extract_text(path: Path) -> str:
    with pymupdf.open(path) as doc:
        pages = [_page_text(page) for page in doc]
    return "\n\n".join(p for p in pages if p).strip() + "\n"


def _page_text(page: pymupdf.Page) -> str:
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    return "\n".join(b[4].strip() for b in _reading_order(blocks, page.rect))


def _reading_order(blocks: list[tuple], rect: pymupdf.Rect) -> list[tuple]:
    """Two-column aware order: full-width blocks split the page into bands; each band is read
    column by column (right column first when the page is mostly Arabic)."""
    mid = rect.x0 + rect.width / 2
    tol = rect.width * _COLUMN_TOLERANCE
    left = [b for b in blocks if b[2] <= mid + tol]
    right = [b for b in blocks if b[0] >= mid - tol and b[2] > mid + tol]
    spanning = [b for b in blocks if b not in left and b not in right]
    if not left or not right:
        return sorted(blocks, key=lambda b: (round(b[1]), b[0]))

    first, second = (right, left) if is_mostly_arabic("".join(b[4] for b in blocks)) else (left, right)
    ordered: list[tuple] = []
    top = -math.inf
    for separator in [*sorted(spanning, key=lambda b: b[1]), None]:
        bottom = separator[1] if separator else math.inf
        for column in (first, second):
            ordered += sorted((b for b in column if top <= b[1] < bottom), key=lambda b: b[1])
        if separator:
            ordered.append(separator)
            top = separator[1]
    return ordered
