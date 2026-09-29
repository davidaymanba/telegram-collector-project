from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import TABLE_ARGS, Base, TimestampMixin, str_enum
from app.database.enums import ClassificationStatus

if TYPE_CHECKING:
    from app.database.models.file import CollectedFile


class Classification(TimestampMixin, Base):
    __tablename__ = "classifications"
    __table_args__ = (
        Index("ix_classifications_subject_type", "subject_code", "content_type"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("collected_files.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    subject_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[ClassificationStatus] = mapped_column(
        str_enum(ClassificationStatus), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    classifier_version: Mapped[str] = mapped_column(String(32), nullable=False)

    file: Mapped[CollectedFile] = relationship(back_populates="classification")
