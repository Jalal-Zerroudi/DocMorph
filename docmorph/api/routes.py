from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from docmorph.api.jobs import JobManager
from docmorph.core.detect import detect
from docmorph.core.models import Format, JobStatus, Mode
from docmorph.engines.pdf_structure import PdfStructureEngine, preferred_device

router = APIRouter(prefix="/api")


def _manager(request: Request) -> JobManager:
    return request.app.state.manager


def _parse_enum(enum, value: str, label: str):
    try:
        return enum(value.lower())
    except ValueError:
        raise HTTPException(422, f"{label} inconnu : {value}") from None


@router.get("/formats")
def formats(request: Request) -> dict:
    manager = _manager(request)
    registry = manager.registry
    unavailable = []
    device = None
    for engine in registry.engines:
        reason = registry.unavailable_reason(engine)
        if reason is not None:
            unavailable.append({"engine": engine.label, "reason": reason})
        elif isinstance(engine, PdfStructureEngine):
            device = preferred_device()
    return {
        "conversions": registry.matrix(),
        "unavailable": unavailable,
        "structure_device": device,
        "max_upload_mb": manager.storage.max_bytes // (1024 * 1024),
    }


@router.post("/detect")
def detect_file(request: Request, file: UploadFile = File(...)) -> dict:
    manager = _manager(request)
    scratch = manager.storage.scratch_file()
    try:
        manager.storage.save(file.file, scratch)
        detection = detect(scratch, file.filename)
    finally:
        scratch.unlink(missing_ok=True)
    return {
        "filename": file.filename,
        "format": detection.format.value,
        "pdf_kind": detection.pdf_kind.value if detection.pdf_kind else None,
        "pages": detection.pages,
        "scanned_pages": detection.scanned_pages,
        "targets": [
            {"target": o.target.value, "modes": [m.value for m in o.modes]}
            for o in manager.registry.options(detection)
        ],
    }


@router.post("/convert")
def convert(
    request: Request,
    files: list[UploadFile] = File(...),
    target: str = Form(...),
    mode: str = Form(Mode.AUTO.value),
) -> dict:
    target_format = _parse_enum(Format, target, "Format cible")
    requested_mode = _parse_enum(Mode, mode, "Mode")
    batch_id, jobs = _manager(request).submit(
        [(f.filename or "document", f.file) for f in files], target_format, requested_mode
    )
    return {"batch_id": batch_id, "jobs": [j.to_dict() for j in jobs]}


@router.get("/jobs/{job_id}")
def job_status(request: Request, job_id: str) -> dict:
    job = _manager(request).get(job_id)
    if job is None:
        raise HTTPException(404, "Tâche inconnue ou expirée.")
    return job.to_dict()


@router.get("/batches/{batch_id}")
def batch_status(request: Request, batch_id: str) -> dict:
    jobs = _manager(request).batch(batch_id)
    if jobs is None:
        raise HTTPException(404, "Lot inconnu ou expiré.")
    return {"batch_id": batch_id, "jobs": [j.to_dict() for j in jobs]}


@router.get("/jobs/{job_id}/download")
def download(request: Request, job_id: str) -> FileResponse:
    job = _manager(request).get(job_id)
    if job is None or job.status != JobStatus.DONE or job.output is None:
        raise HTTPException(404, "Aucun fichier converti pour cette tâche.")
    return FileResponse(job.output, filename=job.output_name)


@router.get("/batches/{batch_id}/zip")
def download_zip(request: Request, batch_id: str) -> FileResponse:
    manager = _manager(request)
    if manager.batch(batch_id) is None:
        raise HTTPException(404, "Lot inconnu ou expiré.")
    archive = manager.build_zip(batch_id)
    return FileResponse(archive, filename=f"docmorph-{batch_id}.zip", media_type="application/zip")
