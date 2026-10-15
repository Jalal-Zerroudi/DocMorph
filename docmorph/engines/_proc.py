from __future__ import annotations

import os
import signal
import subprocess

from docmorph.core.errors import ConversionFailed, Timeout

_LOG_TAIL_CHARS = 2000


def run(cmd: list[str], timeout: float, what: str, env: dict[str, str] | None = None) -> str:
    """Run a command in its own process group; kill the whole group on timeout. Returns stdout."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=True,
        env={**os.environ, **(env or {})},
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise Timeout(f"{what} : délai dépassé ({int(timeout)} s).") from exc
    if proc.returncode != 0:
        raise ConversionFailed(f"{what} a échoué.", detail=tail(err or out))
    return out


def tail(text: str) -> str:
    text = text.strip()
    return text[-_LOG_TAIL_CHARS:]
