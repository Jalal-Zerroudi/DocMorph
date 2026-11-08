"""Runtime settings, overridable through DOCMORPH_* environment variables."""

from __future__ import annotations

import math
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


def _positive_int(name: str, default: str) -> int:
    raw = os.environ.get(name, default)
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be a positive integer, got {raw!r}.") from None
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {raw!r}.")
    return value


def _positive_float(name: str, default: str) -> float:
    raw = os.environ.get(name, default)
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a finite positive number, got {raw!r}.") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number, got {raw!r}.")
    return value


def load_settings() -> Settings:
    default_artifacts = Path.home() / ".cache" / "docling" / "models"
    artifacts = os.environ.get("DOCLING_ARTIFACTS_PATH") or (
        str(default_artifacts) if default_artifacts.is_dir() else ""
    )
    return Settings(
        data_dir=Path(os.environ.get("DOCMORPH_DATA", Path.home() / ".cache" / "docmorph")),
        ttl_hours=_positive_float("DOCMORPH_TTL_HOURS", "24"),
        max_upload_mb=_positive_int("DOCMORPH_MAX_UPLOAD_MB", "200"),
        ocr_langs=tuple(os.environ.get("DOCMORPH_OCR_LANGS", "fra+eng+ara").split("+")),
        device=os.environ.get("DOCMORPH_DEVICE", "auto").lower(),
        docling_artifacts=Path(artifacts) if artifacts else None,
        workers=_positive_int("DOCMORPH_WORKERS", "3"),
    )


settings = load_settings()
