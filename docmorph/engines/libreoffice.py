from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from docmorph.core.engine import Engine
from docmorph.core.errors import ConversionFailed
from docmorph.core.models import Format, Resource, Route
from docmorph.engines import _proc

_TIMEOUT_S = 300

_TO_PDF_SOURCES = (
    Format.DOC, Format.DOCX, Format.XLS, Format.XLSX, Format.PPT, Format.PPTX,
    Format.ODT, Format.ODS, Format.ODP, Format.TXT, Format.RTF,
)

# Explicit export filters: the right one depends on the target, not on the source application.
_FILTERS = {
    Format.PDF: "pdf",
    Format.DOCX: "docx:MS Word 2007 XML",
    Format.DOC: "doc:MS Word 97",
}


class LibreOfficeEngine(Engine):
    name = "libreoffice"
    label = "LibreOffice (headless)"
    resource = Resource.LIBREOFFICE
    routes = (
        *(Route(src, Format.PDF) for src in _TO_PDF_SOURCES),
        Route(Format.TXT, Format.DOCX),
        Route(Format.RTF, Format.DOCX),
        Route(Format.DOCX, Format.DOC),
    )

    def availability(self) -> str | None:
        return None if _soffice() else "LibreOffice n'est pas installé (paquet libreoffice-core)."

    def convert(self, src: Path, dst: Path, route: Route) -> None:
        soffice = _soffice()
        assert soffice is not None
        with tempfile.TemporaryDirectory(prefix="docmorph-lo-") as tmp:
            tmp_path = Path(tmp)
            # A private profile per call: concurrent soffice instances sharing one profile deadlock.
            profile = (tmp_path / "profile").as_uri()
            outdir = tmp_path / "out"
            cmd = [
                soffice,
                f"-env:UserInstallation={profile}",
                "--headless", "--norestore", "--nologo", "--nodefault", "--nolockcheck",
            ]
            if route.source == Format.TXT:
                cmd.append(f"--infilter=Text (encoded):{_text_charset(src)}")
            cmd += ["--convert-to", _FILTERS[route.target], "--outdir", str(outdir), str(src)]
            _proc.run(cmd, _TIMEOUT_S, "LibreOffice")
            produced = outdir / f"{src.stem}{route.target.extension}"
            if not produced.is_file() or produced.stat().st_size == 0:
                raise ConversionFailed("LibreOffice n'a produit aucun fichier.")
            shutil.move(produced, dst)


def _soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def _text_charset(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "UNICODE"
    try:
        data.decode("utf-8")
        return "UTF8"
    except UnicodeDecodeError:
        return "MS_1252"
