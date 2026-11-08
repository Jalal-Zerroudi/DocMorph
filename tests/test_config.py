from __future__ import annotations

import pytest

from docmorph.config import load_settings


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DOCMORPH_MAX_UPLOAD_MB", "0"),
        ("DOCMORPH_MAX_UPLOAD_MB", "-1"),
        ("DOCMORPH_MAX_UPLOAD_MB", "large"),
        ("DOCMORPH_WORKERS", "0"),
        ("DOCMORPH_WORKERS", "-2"),
        ("DOCMORPH_WORKERS", "many"),
        ("DOCMORPH_TTL_HOURS", "0"),
        ("DOCMORPH_TTL_HOURS", "-0.5"),
        ("DOCMORPH_TTL_HOURS", "nan"),
        ("DOCMORPH_TTL_HOURS", "forever"),
    ],
)
def test_numeric_settings_must_be_positive(monkeypatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        load_settings()


def test_numeric_settings_accept_positive_overrides(monkeypatch) -> None:
    monkeypatch.setenv("DOCMORPH_MAX_UPLOAD_MB", "512")
    monkeypatch.setenv("DOCMORPH_WORKERS", "4")
    monkeypatch.setenv("DOCMORPH_TTL_HOURS", "0.5")

    settings = load_settings()

    assert settings.max_upload_mb == 512
    assert settings.workers == 4
    assert settings.ttl_hours == 0.5
