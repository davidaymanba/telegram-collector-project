from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import TABLE_ARGS, Base, TimestampMixin, UTCDateTime, str_enum
from app.database.enums import ChannelStatus

if TYPE_CHECKING:
    from app.database.models.message import Message


class Channel(TimestampMixin, Base):
    __tablename__ = "channels"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_message_id: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[ChannelStatus] = mapped_column(
        str_enum(ChannelStatus), default=ChannelStatus.IDLE, nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    messages: Mapped[list[Message]] = relationship(
        back_populates="channel", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Channel {self.id} {self.username or self.telegram_id}>"
