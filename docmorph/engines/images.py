from __future__ import annotations

import io
from pathlib import Path

import img2pdf
from PIL import Image

from docmorph.core.engine import Engine
from docmorph.core.errors import ConversionFailed
from docmorph.core.models import Format, Resource, Route


class ImageToPdfEngine(Engine):
    name = "img2pdf"
    label = "img2pdf"
    resource = Resource.CPU
    routes = (Route(Format.JPG, Format.PDF), Route(Format.PNG, Format.PDF))

    def availability(self) -> str | None:
        return None

    def convert(self, src: Path, dst: Path, route: Route) -> None:
        try:
            data = img2pdf.convert(str(src), rotation=img2pdf.Rotation.ifvalid)
        except img2pdf.AlphaChannelError:
            # PDF images cannot carry this alpha channel losslessly; img2pdf refuses, so flatten on white.
            data = img2pdf.convert(_flatten_alpha(src))
        except Exception as exc:
            raise ConversionFailed("Image illisible ou format d'image non pris en charge.", detail=str(exc)) from exc
        dst.write_bytes(data)


def _flatten_alpha(src: Path) -> bytes:
    with Image.open(src) as img:
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        buf = io.BytesIO()
        background.save(buf, format="PNG", dpi=img.info.get("dpi", (96, 96)))
        return buf.getvalue()
