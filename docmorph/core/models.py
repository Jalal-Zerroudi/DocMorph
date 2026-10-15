from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Format(StrEnum):
    PDF = "pdf"
    DOC = "doc"
    DOCX = "docx"
    XLS = "xls"
    XLSX = "xlsx"
    PPT = "ppt"
    PPTX = "pptx"
    ODT = "odt"
    ODS = "ods"
    ODP = "odp"
    TXT = "txt"
    RTF = "rtf"
    JPG = "jpg"
    PNG = "png"

    @property
    def extension(self) -> str:
        return f".{self.value}"


class PdfKind(StrEnum):
    DIGITAL = "digital"
    SCANNED = "scanned"


class Mode(StrEnum):
    """Conversion mode. Only PDF to Word offers a real choice (layout / structure)."""

    AUTO = "auto"
    STANDARD = "standard"
    LAYOUT = "layout"
    STRUCTURE = "structure"


class Resource(StrEnum):
    """Shared resource an engine needs; the job manager limits concurrency per resource."""

    CPU = "cpu"
    LIBREOFFICE = "libreoffice"
    GPU = "gpu"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class Detection:
    format: Format
    pdf_kind: PdfKind | None = None
    mime: str | None = None
    pages: int | None = None
    scanned_pages: int | None = None


@dataclass(frozen=True)
class Route:
    source: Format
    target: Format
    mode: Mode = Mode.STANDARD
    pdf_kind: PdfKind | None = None

    def accepts(self, detection: Detection) -> bool:
        if detection.format != self.source:
            return False
        return self.pdf_kind is None or self.pdf_kind == detection.pdf_kind
