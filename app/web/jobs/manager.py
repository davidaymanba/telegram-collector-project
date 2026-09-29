"""Run CLI commands (collect/process) as subprocesses and stream their logs over SSE.

The subprocess is the *same* CLI launchd runs, so locking, run records and logging behave
identically regardless of who started a job. Its JSON log lines are parsed to drive live
progress and counters in the dashboard.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from app.config import PROJECT_ROOT, Settings
from app.runtime.lock import EXIT_LOCKED, lock_status

JobKind = Literal["collect", "process", "reclassify"]
JobState = Literal["queued", "running", "succeeded", "failed", "locked"]
MAX_LINES = 5000


class JobConflictError(RuntimeError):
    def __init__(self, holder: dict[str, Any] | None) -> None:
        self.holder = holder
        super().__init__("Another job is already running")


@dataclass
class Job:
    id: str
    kind: JobKind
    args: list[str]
    state: JobState = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    exit_code: int | None = None
    run_id: int | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    lines: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_LINES))
    seq: int = 0
    _cond: threading.Condition = field(default_factory=threading.Condition, repr=False)

    @property
    def done(self) -> bool:
        return self.state in ("succeeded", "failed", "locked")

    def append(self, entry: dict[str, Any]) -> None:
        with self._cond:
            self.seq += 1
            entry["seq"] = self.seq
            self.lines.append(entry)
            self._cond.notify_all()

    def since(self, seq: int) -> list[dict[str, Any]]:
        with self._cond:
            return [e for e in self.lines if e["seq"] > seq]

    def wait(self, seq: int, timeout: float) -> None:
        with self._cond:
            if self.seq <= seq and not self.done:
                self._cond.wait(timeout)

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id, "kind": self.kind, "args": self.args, "state": self.state,
            "created_at": self.created_at, "finished_at": self.finished_at,
            "exit_code": self.exit_code, "run_id": self.run_id, "progress": self.progress,
            "counters": self.counters, "line_count": self.seq,
        }


def parse_line(raw: str) -> dict[str, Any]:
    raw = raw.rstrip("\n")
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "event" in data:
            return {
                "ts": data.pop("timestamp", None),
                "level": str(data.pop("level", "info")).lower(),
                "event": str(data.pop("event")),
                "logger": data.pop("logger", None),
                "fields": data,
            }
    except ValueError:
        pass
    return {"ts": datetime.now(UTC).isoformat(), "level": "info", "event": raw, "fields": {},
            "logger": None}


class JobManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jobs: dict[str, Job] = {}
        self._order: deque[str] = deque(maxlen=50)
        self._lock = threading.Lock()

    def active(self) -> Job | None:
        with self._lock:
            return next((j for j in self._jobs.values() if not j.done), None)

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def recent(self) -> list[Job]:
        return [self._jobs[i] for i in reversed(self._order) if i in self._jobs]

    def start(self, kind: JobKind, args: list[str]) -> Job:
        with self._lock:
            if any(not j.done for j in self._jobs.values()):
                raise JobConflictError({"trigger": "web"})
            status = lock_status(self.settings.lock_path)
            if status.locked:
                raise JobConflictError(status.holder)
            job = Job(id=uuid.uuid4().hex[:12], kind=kind, args=args)
            self._jobs[job.id] = job
            self._order.append(job.id)
            if len(self._jobs) > 60:
                for old in list(self._jobs)[:10]:
                    if self._jobs[old].done:
                        del self._jobs[old]
        cmd = [sys.executable, "-m", "app.cli", kind, *args, "--trigger", "web"]
        env = {**os.environ, "TUC_LOG_FORMAT": "json", "PYTHONUNBUFFERED": "1",
               "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen(
            cmd, cwd=PROJECT_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        job.state = "running"
        job.append({"ts": job.created_at.isoformat(), "level": "info", "event": "job_started",
                    "fields": {"command": " ".join(["app.cli", kind, *args])}, "logger": "web"})
        threading.Thread(target=self._pump, args=(job, proc), daemon=True,
                         name=f"job-{job.id}").start()
        return job

    def _pump(self, job: Job, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            if not raw.strip():
                continue
            entry = parse_line(raw)
            f = entry["fields"]
            if entry["event"] == "run_started" and "run_id" in f:
                job.run_id = int(f["run_id"])
            if entry["event"] == "progress":
                job.progress = {k: f.get(k) for k in ("current", "total", "channel", "file_id")
                                if f.get(k) is not None}
                if isinstance(f.get("counters"), dict):
                    job.counters = {k: int(v) for k, v in f["counters"].items()}
            if entry["event"] == "run_finished" and isinstance(f.get("counters"), dict):
                job.counters = {k: int(v) for k, v in f["counters"].items()}
            job.append(entry)
        code = proc.wait()
        job.exit_code = code
        job.finished_at = datetime.now(UTC)
        job.state = "succeeded" if code == 0 else "locked" if code == EXIT_LOCKED else "failed"
        job.append({"ts": job.finished_at.isoformat(), "level": "info" if code == 0 else "error",
                    "event": "job_finished", "fields": {"exit_code": code, "state": job.state},
                    "logger": "web"})
