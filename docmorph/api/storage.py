from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from docmorph.core.errors import FileTooLarge

_CHUNK = 1024 * 1024


class Storage:
    def __init__(self, root: Path, max_upload_mb: int) -> None:
        self.root = root
        self.max_bytes = max_upload_mb * 1024 * 1024
        self.jobs_dir = root / "jobs"
        self.batches_dir = root / "batches"
        self.scratch_dir = root / "scratch"

    def reset(self) -> None:
        """Job state lives in memory: files left by a previous run can no longer be served."""
        for directory in (self.jobs_dir, self.batches_dir, self.scratch_dir):
            shutil.rmtree(directory, ignore_errors=True)
            directory.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        path = self.jobs_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def scratch_file(self) -> Path:
        return self.scratch_dir / uuid.uuid4().hex

    def save(self, stream: BinaryIO, dest: Path) -> int:
        written = 0
        with dest.open("wb") as out:
            while chunk := stream.read(_CHUNK):
                written += len(chunk)
                if written > self.max_bytes:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise FileTooLarge(f"Fichier trop volumineux (maximum {self.max_bytes // (1024 * 1024)} Mo).")
                out.write(chunk)
        return written

    def remove_job(self, job_id: str) -> None:
        shutil.rmtree(self.jobs_dir / job_id, ignore_errors=True)

    def remove_batch(self, batch_id: str) -> None:
        (self.batches_dir / f"{batch_id}.zip").unlink(missing_ok=True)
