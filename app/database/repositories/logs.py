from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.database.enums import ProcessingLogStatus
from app.database.models import ProcessingLog
from app.database.repositories.base import Repository


class ProcessingLogRepository(Repository[ProcessingLog]):
    model = ProcessingLog

    def record(
        self,
        *,
        stage: str,
        status: ProcessingLogStatus,
        file_id: int | None = None,
        run_id: int | None = None,
        message: str | None = None,
        error: str | None = None,
    ) -> ProcessingLog:
        return self.add(
            ProcessingLog(
                file_id=file_id,
                run_id=run_id,
                stage=stage,
                status=status,
                message=(message or "")[:1000] or None,
                error_message=error,
            )
        )

    def for_file(self, file_id: int) -> Sequence[ProcessingLog]:
        return self.session.scalars(
            select(ProcessingLog)
            .where(ProcessingLog.file_id == file_id)
            .order_by(ProcessingLog.created_at, ProcessingLog.id)
        ).all()

    def for_run(self, run_id: int, limit: int = 500) -> Sequence[ProcessingLog]:
        return self.session.scalars(
            select(ProcessingLog)
            .where(ProcessingLog.run_id == run_id)
            .order_by(ProcessingLog.id)
            .limit(limit)
        ).all()
