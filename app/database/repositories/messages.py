from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app.database.models import Message
from app.database.repositories.base import Page, Repository


class MessageRepository(Repository[Message]):
    model = Message

    def get_by_telegram_id(self, channel_id: int, telegram_message_id: int) -> Message | None:
        return self.session.scalar(
            select(Message).where(
                Message.channel_id == channel_id,
                Message.telegram_message_id == telegram_message_id,
            )
        )

    def search(
        self,
        *,
        q: str | None = None,
        channel_id: int | None = None,
        media_type: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Page[Message]:
        stmt = select(Message)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Message.caption.like(like), Message.file_name.like(like)))
        if channel_id:
            stmt = stmt.where(Message.channel_id == channel_id)
        if media_type:
            stmt = stmt.where(Message.media_type == media_type)
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.session.scalars(
            stmt.options(joinedload(Message.channel), joinedload(Message.file))
            .order_by(Message.message_date.desc(), Message.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().all()
        return Page(list(items), int(total), page, page_size)
