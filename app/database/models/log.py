from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import TABLE_ARGS, Base, UTCDateTime, str_enum
from app.database.enums import ProcessingLogStatus


class ProcessingLog(Base):
    __tablename__ = "processing_logs"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int | None] = mapped_column(
        ForeignKey("collected_files.id", ondelete="CASCADE"), index=True, nullable=True
    )
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("processing_runs.id", ondelete="SET NULL"), index=True, nullable=True
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[ProcessingLogStatus] = mapped_column(
        str_enum(ProcessingLogStatus), nullable=False
    )
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(UTC), nullable=False
    )
