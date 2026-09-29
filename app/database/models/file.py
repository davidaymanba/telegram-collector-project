from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CHAR, BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import TABLE_ARGS, Base, TimestampMixin, str_enum
from app.database.enums import FileStatus

if TYPE_CHECKING:
    from app.database.models.classification import Classification
    from app.database.models.message import Message


class CollectedFile(TimestampMixin, Base):
    __tablename__ = "collected_files"
    __table_args__ = (
        Index("ix_collected_files_status_created", "status", "created_at"),
        Index("ix_collected_files_extension", "extension"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    telegram_document_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, nullable=True
    )
    duplicate_of_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("collected_files.id", ondelete="SET NULL"), nullable=True
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extension: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(CHAR(64), index=True, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    extracted_text_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[FileStatus] = mapped_column(
        str_enum(FileStatus), default=FileStatus.DISCOVERED, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    message: Mapped[Message] = relationship(back_populates="file")
    classification: Mapped[Classification | None] = relationship(
        back_populates="file", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
