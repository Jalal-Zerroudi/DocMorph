from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from docmorph.core.engine import Engine
from docmorph.core.errors import ConversionFailed
from docmorph.core.models import Format, Mode, PdfKind, Resource, Route
from docmorph.engines import _proc

_TIMEOUT_S = 900


class PdfLayoutEngine(Engine):
    """pdf2docx, run in a child process so a crash or hang cannot take the server down."""

    name = "pdf2docx"
    label = "pdf2docx (mise en page)"
    resource = Resource.CPU
    routes = (Route(Format.PDF, Format.DOCX, Mode.LAYOUT, PdfKind.DIGITAL),)

    def availability(self) -> str | None:
        if importlib.util.find_spec("pdf2docx") is None:
            return "Le paquet Python pdf2docx n'est pas installé."
        return None

    def convert(self, src: Path, dst: Path, route: Route) -> None:
        cmd = [sys.executable, "-m", "docmorph.engines._pdf2docx_worker", str(src), str(dst)]
        _proc.run(cmd, _TIMEOUT_S, "pdf2docx")
        if not dst.is_file() or dst.stat().st_size == 0:
            raise ConversionFailed("pdf2docx n'a produit aucun fichier.")
