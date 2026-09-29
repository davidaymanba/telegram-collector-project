from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import TABLE_ARGS, Base, TimestampMixin, UTCDateTime

if TYPE_CHECKING:
    from app.database.models.channel import Channel
    from app.database.models.file import CollectedFile


class Message(TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("channel_id", "telegram_message_id"),
        Index("ix_messages_message_date", "message_date"),
        TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_date: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    channel: Mapped[Channel] = relationship(back_populates="messages")
    file: Mapped[CollectedFile | None] = relationship(
        back_populates="message", uselist=False, cascade="all, delete-orphan",
        passive_deletes=True,
    )
