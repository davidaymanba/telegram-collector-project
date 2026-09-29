from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import TABLE_ARGS, Base, UTCDateTime, str_enum
from app.database.enums import RunKind, RunTrigger


class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[RunKind] = mapped_column(str_enum(RunKind), nullable=False, index=True)
    trigger: Mapped[RunTrigger] = mapped_column(str_enum(RunTrigger), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    new_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    classified_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unclassified_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unsupported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    @property
    def duration_seconds(self) -> float | None:
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()
