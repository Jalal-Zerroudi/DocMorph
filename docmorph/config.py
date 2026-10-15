"""Runtime settings, overridable through DOCMORPH_* environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    ttl_hours: float
    max_upload_mb: int
    ocr_langs: tuple[str, ...]
    device: str
    docling_artifacts: Path | None
    workers: int


def load_settings() -> Settings:
    default_artifacts = Path.home() / ".cache" / "docling" / "models"
    artifacts = os.environ.get("DOCLING_ARTIFACTS_PATH") or (
        str(default_artifacts) if default_artifacts.is_dir() else ""
    )
    return Settings(
        data_dir=Path(os.environ.get("DOCMORPH_DATA", Path.home() / ".cache" / "docmorph")),
        ttl_hours=float(os.environ.get("DOCMORPH_TTL_HOURS", "24")),
        max_upload_mb=int(os.environ.get("DOCMORPH_MAX_UPLOAD_MB", "200")),
        ocr_langs=tuple(os.environ.get("DOCMORPH_OCR_LANGS", "fra+eng+ara").split("+")),
        device=os.environ.get("DOCMORPH_DEVICE", "auto").lower(),
        docling_artifacts=Path(artifacts) if artifacts else None,
        workers=int(os.environ.get("DOCMORPH_WORKERS", "3")),
    )


settings = load_settings()
