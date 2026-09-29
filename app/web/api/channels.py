from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.database.enums import ChannelStatus
from app.database.models import Channel
from app.database.repositories import ChannelRepository
from app.web.deps import DB, User
from app.web.schemas import ChannelIn, ChannelOut, ChannelPatch

router = APIRouter(prefix="/channels", tags=["channels"])


def _out(ch: Channel, counts: dict[int, int]) -> ChannelOut:
    out = ChannelOut.model_validate(ch)
    out.file_count = counts.get(ch.id, 0)
    return out


def _get(repo: ChannelRepository, channel_id: int) -> Channel:
    ch = repo.get(channel_id)
    if ch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel not found")
    return ch


@router.get("", response_model=list[ChannelOut])
def list_channels(db: DB, _: User) -> list[ChannelOut]:
    repo = ChannelRepository(db)
    counts = repo.file_counts()
    return [_out(c, counts) for c in repo.list_all()]


@router.post("", response_model=ChannelOut, status_code=201)
def create_channel(body: ChannelIn, db: DB, _: User) -> ChannelOut:
    if not body.username and body.telegram_id is None:
        raise HTTPException(422, "Provide a username or a Telegram id")
    ch = Channel(name=body.name, username=body.username, telegram_id=body.telegram_id,
                 enabled=body.enabled, last_message_id=0,
                 status=ChannelStatus.IDLE if body.enabled else ChannelStatus.DISABLED)
    try:
        ChannelRepository(db).add(ch)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A channel with this username or Telegram id exists") from exc
    return _out(ch, {})


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel(channel_id: int, body: ChannelPatch, db: DB, _: User) -> ChannelOut:
    repo = ChannelRepository(db)
    ch = _get(repo, channel_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(ch, key, value)
    if body.enabled is not None:
        if not body.enabled:
            ch.status = ChannelStatus.DISABLED
        elif ch.status == ChannelStatus.DISABLED:
            ch.status = ChannelStatus.IDLE
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A channel with this username or Telegram id exists") from exc
    return _out(ch, repo.file_counts())


@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel_id: int, db: DB, _: User) -> None:
    repo = ChannelRepository(db)
    repo.delete(_get(repo, channel_id))
