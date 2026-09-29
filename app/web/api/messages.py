from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.database.repositories import MessageRepository
from app.web.deps import DB, User
from app.web.schemas import MessageOut, PageOut

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=PageOut[MessageOut])
def list_messages(
    db: DB,
    _: User,
    q: str | None = None,
    channel_id: int | None = None,
    media_type: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> PageOut[MessageOut]:
    result = MessageRepository(db).search(q=q, channel_id=channel_id, media_type=media_type,
                                          page=page, page_size=page_size)
    items = []
    for m in result.items:
        out = MessageOut.model_validate(m)
        if m.file is not None:
            out.file_id = m.file.id
            out.file_status = m.file.status
        items.append(out)
    return PageOut[MessageOut](items=items, total=result.total, page=page, page_size=page_size,
                               pages=result.pages)
