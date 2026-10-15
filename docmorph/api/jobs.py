from __future__ import annotations

import logging
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from docmorph.api.storage import Storage
from docmorph.core.detect import detect
from docmorph.core.errors import ConversionFailed, ConversionNotAvailable, DocMorphError
from docmorph.core.models import Detection, Format, JobStatus, Mode, Resource
from docmorph.core.registry import Registry, Step

log = logging.getLogger(__name__)

_PURGE_INTERVAL_S = 15 * 60


@dataclass
class Job:
    id: str
    batch_id: str
    filename: str
    target: Format
    requested_mode: Mode
    status: JobStatus = JobStatus.QUEUED
    detection: Detection | None = None
    mode_used: Mode | None = None
    error: dict[str, str | None] | None = None
    output: Path | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    @property
    def output_name(self) -> str:
        return f"{Path(self.filename).stem or 'document'}{self.target.extension}"

    def fail(self, error: DocMorphError) -> None:
        self.status = JobStatus.FAILED
        self.error = error.to_dict()
        self.finished_at = time.time()

    def to_dict(self) -> dict:
        d = self.detection
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "filename": self.filename,
            "source_format": d.format.value if d else None,
            "pdf_kind": d.pdf_kind.value if d and d.pdf_kind else None,
            "target": self.target.value,
            "requested_mode": self.requested_mode.value,
            "mode_used": self.mode_used.value if self.mode_used else None,
            "status": self.status.value,
            "error": self.error,
            "output_name": self.output_name if self.status == JobStatus.DONE else None,
            "duration_s": round(self.finished_at - self.created_at, 1) if self.finished_at else None,
        }


class JobManager:
    def __init__(self, registry: Registry, storage: Storage, workers: int, ttl_hours: float) -> None:
        self.registry = registry
        self.storage = storage
        self.ttl_s = ttl_hours * 3600
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="docmorph-job")
        self._semaphores = {
            Resource.GPU: threading.Semaphore(1),
            Resource.LIBREOFFICE: threading.Semaphore(2),
            Resource.CPU: threading.Semaphore(workers),
        }
        self._jobs: dict[str, Job] = {}
        self._batches: dict[str, list[str]] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._purger = threading.Thread(target=self._purge_loop, name="docmorph-purge", daemon=True)

    def start(self) -> None:
        self.storage.reset()
        self._purger.start()

    def shutdown(self) -> None:
        self._stop.set()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def submit(self, files: list[tuple[str, BinaryIO]], target: Format, mode: Mode) -> tuple[str, list[Job]]:
        batch_id = uuid.uuid4().hex[:12]
        jobs = []
        for filename, stream in files:
            job = Job(id=uuid.uuid4().hex[:12], batch_id=batch_id, filename=filename, target=target, requested_mode=mode)
            with self._lock:
                self._jobs[job.id] = job
            jobs.append(job)
            try:
                source, plan = self._prepare(job, stream)
            except DocMorphError as exc:
                job.fail(exc)
                continue
            self._executor.submit(self._run, job, source, plan)
        with self._lock:
            self._batches[batch_id] = [j.id for j in jobs]
        return batch_id, jobs

    def _prepare(self, job: Job, stream: BinaryIO) -> tuple[Path, list[Step]]:
        workdir = self.storage.job_dir(job.id)
        upload = workdir / "upload"
        self.storage.save(stream, upload)
        job.detection = detect(upload, job.filename)
        plan = self.registry.resolve(job.detection, job.target, job.requested_mode)
        # Engines such as LibreOffice rely on the extension, so name the input after the detected format.
        source = upload.rename(workdir / f"input{job.detection.format.extension}")
        return source, plan

    def _run(self, job: Job, source: Path, plan: list[Step]) -> None:
        job.status = JobStatus.RUNNING
        workdir = source.parent
        current = source
        try:
            for index, step in enumerate(plan):
                last = index == len(plan) - 1
                out = workdir / (f"output{job.target.extension}" if last else f"step{index}{step.route.target.extension}")
                with self._semaphores[step.engine.resource]:
                    step.engine.convert(current, out, step.route)
                if not out.is_file() or out.stat().st_size == 0:
                    raise ConversionFailed(f"{step.engine.label} n'a produit aucun fichier.")
                current = out
        except DocMorphError as exc:
            log.warning("job %s failed: %s (%s)", job.id, exc.message, exc.detail)
            job.fail(exc)
            return
        except Exception as exc:
            log.exception("job %s crashed", job.id)
            job.fail(ConversionFailed("Erreur inattendue pendant la conversion.", detail=repr(exc)))
            return
        job.output = current
        job.mode_used = plan[0].mode
        job.status = JobStatus.DONE
        job.finished_at = time.time()

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def batch(self, batch_id: str) -> list[Job] | None:
        with self._lock:
            ids = self._batches.get(batch_id)
            return None if ids is None else [self._jobs[i] for i in ids if i in self._jobs]

    def build_zip(self, batch_id: str) -> Path:
        jobs = self.batch(batch_id) or []
        done = [j for j in jobs if j.status == JobStatus.DONE and j.output]
        if not done:
            raise ConversionNotAvailable("Aucun fichier converti à télécharger dans ce lot.")
        archive = self.storage.batches_dir / f"{batch_id}.zip"
        used: set[str] = set()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for job in done:
                zf.write(job.output, _unique_name(job.output_name, used))
        return archive

    def _purge_loop(self) -> None:
        while not self._stop.wait(_PURGE_INTERVAL_S):
            self.purge_expired()

    def purge_expired(self, now: float | None = None) -> int:
        cutoff = (now or time.time()) - self.ttl_s
        with self._lock:
            expired = [
                j for j in self._jobs.values()
                if j.created_at < cutoff and j.status in (JobStatus.DONE, JobStatus.FAILED)
            ]
            for job in expired:
                del self._jobs[job.id]
            empty = [b for b, ids in self._batches.items() if not any(i in self._jobs for i in ids)]
            for batch_id in empty:
                del self._batches[batch_id]
        for job in expired:
            self.storage.remove_job(job.id)
        for batch_id in empty:
            self.storage.remove_batch(batch_id)
        return len(expired)


def _unique_name(name: str, used: set[str]) -> str:
    candidate, n = name, 1
    stem, suffix = Path(name).stem, Path(name).suffix
    while candidate in used:
        n += 1
        candidate = f"{stem} ({n}){suffix}"
    used.add(candidate)
    return candidate
