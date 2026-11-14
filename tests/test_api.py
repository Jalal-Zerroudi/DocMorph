from __future__ import annotations

import io
import time
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docmorph.api.jobs import Job
from docmorph.api.main import create_app
from docmorph.config import settings
from docmorph.core.engine import Engine
from docmorph.core.models import Format, Mode, Route
from docmorph.engines.images import ImageToPdfEngine
from docmorph.engines.pdf_text import PdfTextEngine


class _CrashingImageEngine(Engine):
    name = "crashing-image"
    label = "Crashing image"
    routes = (Route(Format.JPG, Format.PDF),)

    def availability(self) -> str | None:
        return None

    def convert(self, src: Path, dst: Path, route: Route) -> None:
        raise RuntimeError("sensitive backend detail")


@pytest.fixture
def client(tmp_path: Path):
    config = replace(settings, data_dir=tmp_path / "data", max_upload_mb=1)
    app = create_app(config, engines=[ImageToPdfEngine(), PdfTextEngine()])
    with TestClient(app) as c:
        yield c


def _wait(client: TestClient, batch_id: str) -> list[dict]:
    for _ in range(100):
        jobs = client.get(f"/api/batches/{batch_id}").json()["jobs"]
        if all(j["status"] in ("done", "failed") for j in jobs):
            return jobs
        time.sleep(0.05)
    raise AssertionError("batch did not finish")


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("report.docx", "report.pdf"),
        ("../../report.docx", "report.pdf"),
        (r"C:\fakepath\report.docx", "report.pdf"),
        ("..", "document.pdf"),
        ("\n", "document.pdf"),
    ],
)
def test_output_name_uses_safe_basename(filename: str, expected: str) -> None:
    job = Job(
        id="job",
        batch_id="batch",
        filename=filename,
        target=Format.PDF,
        requested_mode=Mode.AUTO,
    )
    assert job.output_name == expected


def test_formats_only_lists_installed_engines(client: TestClient) -> None:
    rows = client.get("/api/formats").json()["conversions"]
    assert {(r["source"], r["target"]) for r in rows} == {("jpg", "pdf"), ("png", "pdf"), ("pdf", "txt")}


def test_index_page_is_served(client: TestClient) -> None:
    assert "DocMorph" in client.get("/").text


def test_detect(client: TestClient, two_column_pdf: Path) -> None:
    res = client.post("/api/detect", files={"file": ("a.pdf", two_column_pdf.read_bytes())}).json()
    assert res["format"] == "pdf"
    assert res["pdf_kind"] == "digital"
    assert res["targets"] == [{"target": "txt", "modes": ["standard"]}]


def test_batch_conversion_download_and_zip(client: TestClient, png_with_alpha: Path, jpg_file: Path) -> None:
    files = [
        ("files", ("logo.png", png_with_alpha.read_bytes())),
        ("files", ("photo.jpg", jpg_file.read_bytes())),
        ("files", ("notes.txt", b"plain text")),
    ]
    res = client.post("/api/convert", files=files, data={"target": "pdf"}).json()
    jobs = _wait(client, res["batch_id"])
    by_name = {j["filename"]: j for j in jobs}

    assert by_name["logo.png"]["status"] == "done"
    assert by_name["photo.jpg"]["status"] == "done"
    assert by_name["notes.txt"]["status"] == "failed"
    assert by_name["notes.txt"]["error"]["code"] == "conversion_not_available"

    download = client.get(f"/api/jobs/{by_name['logo.png']['id']}/download")
    assert download.content.startswith(b"%PDF")
    assert "logo.pdf" in download.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(client.get(f"/api/batches/{res['batch_id']}/zip").content))
    assert sorted(archive.namelist()) == ["logo.pdf", "photo.pdf"]


def test_zip_disambiguates_duplicate_output_names(
    client: TestClient, png_with_alpha: Path, jpg_file: Path
) -> None:
    files = [
        ("files", ("scan.png", png_with_alpha.read_bytes())),
        ("files", ("scan.jpg", jpg_file.read_bytes())),
    ]
    response = client.post("/api/convert", files=files, data={"target": "pdf"}).json()
    jobs = _wait(client, response["batch_id"])

    assert all(job["status"] == "done" for job in jobs)
    archive_response = client.get(f"/api/batches/{response['batch_id']}/zip")
    with zipfile.ZipFile(io.BytesIO(archive_response.content)) as archive:
        assert set(archive.namelist()) == {"scan.pdf", "scan (2).pdf"}


def test_unexpected_engine_error_does_not_leak_internal_detail(tmp_path: Path, jpg_file: Path) -> None:
    config = replace(settings, data_dir=tmp_path / "data", max_upload_mb=1)
    app = create_app(config, engines=[_CrashingImageEngine()])

    with TestClient(app) as client:
        response = client.post(
            "/api/convert",
            files=[("files", ("photo.jpg", jpg_file.read_bytes()))],
            data={"target": "pdf"},
        ).json()
        job = _wait(client, response["batch_id"])[0]

    assert job["status"] == "failed"
    assert job["error"] == {
        "code": "conversion_failed",
        "message": "Erreur inattendue pendant la conversion.",
        "detail": None,
    }


def test_unsupported_file_fails_cleanly(client: TestClient) -> None:
    res = client.post("/api/convert", files=[("files", ("x.bin", bytes(range(256)) * 4))], data={"target": "pdf"})
    job = res.json()["jobs"][0]
    assert job["status"] == "failed"
    assert job["error"]["code"] == "unsupported_format"


def test_file_too_large(client: TestClient) -> None:
    res = client.post("/api/convert", files=[("files", ("big.txt", b"a" * (2 * 1024 * 1024)))], data={"target": "pdf"})
    assert res.json()["jobs"][0]["error"]["code"] == "file_too_large"


def test_unknown_target_is_rejected(client: TestClient, jpg_file: Path) -> None:
    res = client.post("/api/convert", files=[("files", ("p.jpg", jpg_file.read_bytes()))], data={"target": "exe"})
    assert res.status_code == 422


def test_expired_jobs_are_purged(client: TestClient, jpg_file: Path) -> None:
    res = client.post("/api/convert", files=[("files", ("p.jpg", jpg_file.read_bytes()))], data={"target": "pdf"}).json()
    job_id = _wait(client, res["batch_id"])[0]["id"]
    manager = client.app.state.manager
    assert manager.purge_expired(now=time.time() + 25 * 3600) == 1
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
