from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from app.database.models import Channel, CollectedFile, Message
from app.database.repositories.base import Repository


class ChannelRepository(Repository[Channel]):
    model = Channel

    def list_all(self) -> Sequence[Channel]:
        return self.session.scalars(select(Channel).order_by(Channel.name)).all()

    def list_enabled(self) -> Sequence[Channel]:
        return self.session.scalars(
            select(Channel).where(Channel.enabled.is_(True)).order_by(Channel.id)
        ).all()

    def get_by_username(self, username: str) -> Channel | None:
        return self.session.scalar(
            select(Channel).where(func.lower(Channel.username) == username.lower().lstrip("@"))
        )

    def get_by_telegram_id(self, telegram_id: int) -> Channel | None:
        return self.session.scalar(select(Channel).where(Channel.telegram_id == telegram_id))

    def find(self, ref: str) -> Channel | None:
        """Look a channel up by id, @username, telegram id or exact name."""
        ref = ref.strip()
        if ref.isdigit() and (ch := self.get(int(ref))):
            return ch
        if ref.lstrip("-").isdigit() and (ch := self.get_by_telegram_id(int(ref))):
            return ch
        if ch := self.get_by_username(ref):
            return ch
        return self.session.scalar(select(Channel).where(Channel.name == ref))

    def file_counts(self) -> dict[int, int]:
        rows = self.session.execute(
            select(Message.channel_id, func.count(CollectedFile.id))
            .join(CollectedFile, CollectedFile.message_id == Message.id)
            .group_by(Message.channel_id)
        ).all()
        return {int(cid): int(n) for cid, n in rows}
