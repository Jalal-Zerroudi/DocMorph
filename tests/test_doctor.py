from __future__ import annotations

from dataclasses import replace

from docmorph import doctor


def test_diagnostic_reports_runtime_limits(monkeypatch, capsys, tmp_path) -> None:
    config = replace(
        doctor.settings,
        data_dir=tmp_path,
        ttl_hours=6.5,
        max_upload_mb=42,
        ocr_langs=("fra", "eng"),
        workers=2,
    )
    monkeypatch.setattr(doctor, "settings", config)
    monkeypatch.setattr(doctor, "default_engines", lambda: [])

    doctor.main()

    output = capsys.readouterr().out
    assert f"Dossier temporaire : {tmp_path}" in output
    assert "Langues OCR        : fra+eng" in output
    assert "Taille max/fichier : 42 Mo" in output
    assert "Rétention résultats: 6.5 h" in output
    assert "Workers simultanés : 2" in output
