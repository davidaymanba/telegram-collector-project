from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import joinedload

from app.database.enums import FileStatus
from app.database.models import Classification, CollectedFile, Message
from app.database.repositories.base import Page, Repository

# Files in these states hold (or will hold) real content and can be duplicated against.
_CANONICAL = (
    FileStatus.DOWNLOADED,
    FileStatus.PROCESSING,
    FileStatus.CLASSIFIED,
    FileStatus.UNCLASSIFIED,
)

SortField = Literal["created_at", "original_filename", "size_bytes", "status", "message_date"]


@dataclass(slots=True)
class FileFilters:
    q: str | None = None
    status: list[FileStatus] | None = None
    subject_code: str | None = None
    content_type: str | None = None
    extension: str | None = None
    channel_id: int | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class FileRepository(Repository[CollectedFile]):
    model = CollectedFile

    def get_detail(self, file_id: int) -> CollectedFile | None:
        return self.session.scalar(
            select(CollectedFile)
            .where(CollectedFile.id == file_id)
            .options(
                joinedload(CollectedFile.message).joinedload(Message.channel),
                joinedload(CollectedFile.classification),
            )
        )

    def get_by_message(self, message_id: int) -> CollectedFile | None:
        return self.session.scalar(
            select(CollectedFile).where(CollectedFile.message_id == message_id)
        )

    def find_canonical_by_document_id(self, document_id: int) -> CollectedFile | None:
        return self.session.scalar(
            select(CollectedFile)
            .where(
                CollectedFile.telegram_document_id == document_id,
                CollectedFile.status.in_(_CANONICAL),
            )
            .order_by(CollectedFile.id)
            .limit(1)
        )

    def find_canonical_by_sha256(
        self, sha256: str, exclude_id: int | None = None
    ) -> CollectedFile | None:
        stmt = select(CollectedFile).where(
            CollectedFile.sha256 == sha256, CollectedFile.status.in_(_CANONICAL)
        )
        if exclude_id is not None:
            stmt = stmt.where(CollectedFile.id != exclude_id)
        return self.session.scalar(stmt.order_by(CollectedFile.id).limit(1))

    def list_by_status(
        self, statuses: Sequence[FileStatus], limit: int | None = None,
        file_ids: Sequence[int] | None = None,
    ) -> Sequence[CollectedFile]:
        stmt = (
            select(CollectedFile)
            .where(CollectedFile.status.in_(list(statuses)))
            .options(joinedload(CollectedFile.message).joinedload(Message.channel))
            .order_by(CollectedFile.id)
        )
        if file_ids:
            stmt = stmt.where(CollectedFile.id.in_(list(file_ids)))
        if limit:
            stmt = stmt.limit(limit)
        return self.session.scalars(stmt).unique().all()

    def _filtered(self, f: FileFilters) -> Select[CollectedFile]:
        stmt = (
            select(CollectedFile)
            .join(Message, Message.id == CollectedFile.message_id)
            .outerjoin(Classification, Classification.file_id == CollectedFile.id)
        )
        if f.q:
            like = f"%{f.q}%"
            conds: list[ColumnElement[bool]] = [
                CollectedFile.original_filename.like(like), Message.caption.like(like)
            ]
            if len(f.q) >= 6 and all(c in "0123456789abcdef" for c in f.q.lower()):
                conds.append(CollectedFile.sha256.like(f"{f.q.lower()}%"))
            if f.q.isdigit():
                conds.append(CollectedFile.id == int(f.q))
            stmt = stmt.where(or_(*conds))
        if f.status:
            stmt = stmt.where(CollectedFile.status.in_(f.status))
        if f.subject_code:
            stmt = stmt.where(Classification.subject_code == f.subject_code)
        if f.content_type:
            stmt = stmt.where(Classification.content_type == f.content_type)
        if f.extension:
            stmt = stmt.where(CollectedFile.extension == f.extension.lower().lstrip("."))
        if f.channel_id:
            stmt = stmt.where(Message.channel_id == f.channel_id)
        if f.date_from:
            stmt = stmt.where(CollectedFile.created_at >= f.date_from)
        if f.date_to:
            stmt = stmt.where(CollectedFile.created_at <= f.date_to)
        return stmt

    def search(
        self,
        filters: FileFilters,
        *,
        sort: SortField = "created_at",
        order: Literal["asc", "desc"] = "desc",
        page: int = 1,
        page_size: int = 25,
    ) -> Page[CollectedFile]:
        stmt = self._filtered(filters)
        total = self.session.scalar(
            select(func.count()).select_from(stmt.with_only_columns(CollectedFile.id).subquery())
        ) or 0
        column = Message.message_date if sort == "message_date" else getattr(CollectedFile, sort)
        ordering = column.asc() if order == "asc" else column.desc()
        items = self.session.scalars(
            stmt.options(
                joinedload(CollectedFile.message).joinedload(Message.channel),
                joinedload(CollectedFile.classification),
            )
            .order_by(ordering, CollectedFile.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().all()
        return Page(list(items), int(total), page, page_size)

    def status_counts(self) -> dict[str, int]:
        rows = self.session.execute(
            select(CollectedFile.status, func.count()).group_by(CollectedFile.status)
        ).all()
        return {str(s.value if isinstance(s, FileStatus) else s): int(n) for s, n in rows}

    def extensions(self) -> list[str]:
        return [
            e for e in self.session.scalars(
                select(CollectedFile.extension).distinct().order_by(CollectedFile.extension)
            ) if e
        ]

    def recent(self, limit: int = 10) -> Sequence[CollectedFile]:
        return self.session.scalars(
            select(CollectedFile)
            .options(
                joinedload(CollectedFile.message).joinedload(Message.channel),
                joinedload(CollectedFile.classification),
            )
            .order_by(CollectedFile.created_at.desc(), CollectedFile.id.desc())
            .limit(limit)
        ).unique().all()
