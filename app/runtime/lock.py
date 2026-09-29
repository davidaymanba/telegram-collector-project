"""Cross-process job lock built on `fcntl.flock` (works on macOS and Linux).

The kernel releases the lock automatically if the holder crashes, so there is no stale-lock
cleanup to do. The lock file also carries a small JSON payload describing the holder, which
the dashboard shows ("collect started by launchd 3 minutes ago").
"""

from __future__ import annotations

import fcntl
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

EXIT_LOCKED = 75  # EX_TEMPFAIL


class LockBusyError(RuntimeError):
    def __init__(self, path: Path, holder: dict[str, Any] | None) -> None:
        self.path = path
        self.holder = holder
        who = ""
        if holder:
            who = f" ({holder.get('kind', '?')} via {holder.get('trigger', '?')}, pid {holder.get('pid')})"
        super().__init__(f"Another TUC job is already running{who}. Lock: {path}")


@dataclass(slots=True)
class LockStatus:
    locked: bool
    holder: dict[str, Any] | None


def _read_holder(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
        data = json.loads(raw) if raw else None
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


class JobLock:
    def __init__(self, path: Path, *, kind: str = "job", trigger: str = "cli") -> None:
        self.path = path
        self.kind = kind
        self.trigger = trigger
        self._fd: int | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise LockBusyError(self.path, _read_holder(self.path)) from None
        payload = json.dumps({
            "pid": os.getpid(),
            "kind": self.kind,
            "trigger": self.trigger,
            "started_at": datetime.now(UTC).isoformat(),
        })
        os.ftruncate(fd, 0)
        os.pwrite(fd, payload.encode(), 0)
        self._fd = fd

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            os.ftruncate(self._fd, 0)
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None

    @property
    def held(self) -> bool:
        return self._fd is not None

    def __enter__(self) -> JobLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self.release()


def lock_status(path: Path) -> LockStatus:
    """Probe the lock without holding it."""
    if not path.exists():
        return LockStatus(False, None)
    fd = os.open(path, os.O_RDONLY)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return LockStatus(True, _read_holder(path))
        fcntl.flock(fd, fcntl.LOCK_UN)
        return LockStatus(False, None)
    finally:
        os.close(fd)
