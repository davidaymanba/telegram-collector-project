from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from app.database.enums import RunKind, RunTrigger
from app.database.models import ProcessingRun
from app.database.repositories.base import Page, Repository

COUNTERS = ("new", "duplicate", "classified", "unclassified", "failed", "unsupported")


class RunRepository(Repository[ProcessingRun]):
    model = ProcessingRun

    def start(
        self, kind: RunKind, trigger: RunTrigger, metadata: dict[str, Any] | None = None
    ) -> ProcessingRun:
        return self.add(ProcessingRun(kind=kind, trigger=trigger, metadata_json=metadata or {}))

    def finish(
        self,
        run: ProcessingRun,
        counters: dict[str, int],
        *,
        status: str = "success",
        metadata: dict[str, Any] | None = None,
    ) -> ProcessingRun:
        for name in COUNTERS:
            setattr(run, f"{name}_count", int(counters.get(name, 0)))
        run.finished_at = datetime.now(UTC)
        run.status = status
        if metadata:
            run.metadata_json = {**(run.metadata_json or {}), **metadata}
        self.session.flush()
        return run

    def search(
        self, *, kind: RunKind | None = None, page: int = 1, page_size: int = 25
    ) -> Page[ProcessingRun]:
        stmt = select(ProcessingRun)
        if kind:
            stmt = stmt.where(ProcessingRun.kind == kind)
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.session.scalars(
            stmt.order_by(ProcessingRun.started_at.desc(), ProcessingRun.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return Page(list(items), int(total), page, page_size)

    def latest(self, limit: int = 1) -> Sequence[ProcessingRun]:
        return self.session.scalars(
            select(ProcessingRun).order_by(ProcessingRun.id.desc()).limit(limit)
        ).all()

    def mark_stale_running(self) -> int:
        """Runs left 'running' by a crashed process (lock no longer held) become 'aborted'."""
        stale = self.session.scalars(
            select(ProcessingRun).where(ProcessingRun.status == "running")
        ).all()
        for run in stale:
            run.status = "aborted"
            run.finished_at = run.finished_at or datetime.now(UTC)
        self.session.flush()
        return len(stale)
