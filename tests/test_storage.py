from __future__ import annotations

from pathlib import Path

import pytest

from docmorph.api.storage import Storage


class _FailingStream:
    def __init__(self) -> None:
        self.reads = 0

    def read(self, _: int) -> bytes:
        self.reads += 1
        if self.reads == 1:
            return b"partial document"
        raise OSError("simulated upload failure")


def test_save_removes_partial_file_after_stream_failure(tmp_path: Path) -> None:
    storage = Storage(tmp_path, max_upload_mb=1)
    storage.reset()
    destination = storage.scratch_file()

    with pytest.raises(OSError, match="simulated upload failure"):
        storage.save(_FailingStream(), destination)

    assert not destination.exists()
