"""Shared lifecycle for collect/process runs: lock → ProcessingRun row → per-run log file."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import Settings
from app.database.enums import RunKind, RunTrigger
from app.database.repositories import RunRepository
from app.database.session import session_scope
from app.logging import add_file_handler, get_logger, remove_handler
from app.runtime.lock import JobLock

log = get_logger("tuc.run")


def run_log_path(settings: Settings, run_id: int) -> Path:
    return settings.log_dir / "runs" / f"{run_id}.jsonl"


@dataclass(slots=True)
class RunContext:
    run_id: int
    kind: RunKind
    counters: Counter[str] = field(default_factory=Counter)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "success"

    def bump(self, key: str, n: int = 1) -> None:
        self.counters[key] += n

    def progress(self, current: int, total: int | None = None, **extra: Any) -> None:
        log.info("progress", run_id=self.run_id, current=current, total=total,
                 counters=dict(self.counters), **extra)


@contextmanager
def tracked_run(
    settings: Settings, kind: RunKind, trigger: RunTrigger, metadata: dict[str, Any] | None = None
) -> Iterator[RunContext]:
    """Hold the job lock for the whole run. Raises LockBusyError if another job is active."""
    with JobLock(settings.lock_path, kind=kind.value, trigger=trigger.value):
        with session_scope() as s:
            RunRepository(s).mark_stale_running()
            run = RunRepository(s).start(kind, trigger, metadata)
            run_id = run.id
        ctx = RunContext(run_id=run_id, kind=kind, metadata=dict(metadata or {}))
        handler = add_file_handler(run_log_path(settings, run_id))
        log.info("run_started", run_id=run_id, kind=kind.value, trigger=trigger.value)
        try:
            yield ctx
        except BaseException as exc:
            ctx.status = "failed"
            ctx.metadata["error"] = f"{type(exc).__name__}: {exc}"[:1000]
            log.error("run_failed", run_id=run_id, error=ctx.metadata["error"])
            raise
        finally:
            with session_scope() as s:
                repo = RunRepository(s)
                run_obj = repo.get(run_id)
                if run_obj is not None:
                    repo.finish(run_obj, dict(ctx.counters), status=ctx.status,
                                metadata=ctx.metadata)
            log.info("run_finished", run_id=run_id, status=ctx.status,
                     counters=dict(ctx.counters))
            remove_handler(handler)
