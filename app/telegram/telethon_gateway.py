from __future__ import annotations

import mimetypes
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from telethon import TelegramClient, errors
from telethon.tl.types import (
    DocumentAttributeFilename,
    InputMessagesFilterDocument,
    MessageMediaDocument,
    MessageMediaPhoto,
)

from app.config import Settings
from app.telegram.gateway import (
    ChannelUnavailableError,
    CredentialsMissingError,
    FloodWaitError,
    ProgressCb,
    TgEntity,
    TgMessage,
)


def build_client(settings: Settings) -> TelegramClient:
    if not settings.telegram_configured or settings.telegram_api_hash is None:
        raise CredentialsMissingError(
            "Telegram credentials missing: set TUC_TELEGRAM_API_ID and TUC_TELEGRAM_API_HASH "
            "(get them from https://my.telegram.org)"
        )
    session = settings.telegram_session_path
    session.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(session.parent, 0o700)
    return TelegramClient(
        str(session.with_suffix("") if session.suffix == ".session" else session),
        int(settings.telegram_api_id or 0),
        settings.telegram_api_hash.get_secret_value(),
        flood_sleep_threshold=0,   # we handle FloodWait ourselves, visibly
        device_model="TUC Collector",
        app_version="1.0",
    )


def secure_session_file(settings: Settings) -> None:
    path = settings.telegram_session_file
    if path.exists():
        os.chmod(path, 0o600)


def _to_tg_message(msg: Any) -> TgMessage:
    media = msg.media
    out = TgMessage(id=int(msg.id), date=msg.date, text=msg.message or "", raw=msg,
                    metadata={"grouped_id": msg.grouped_id, "views": getattr(msg, "views", None),
                              "post_author": getattr(msg, "post_author", None)})
    if isinstance(media, MessageMediaDocument) and media.document is not None:
        doc = media.document
        name = next((a.file_name for a in doc.attributes
                     if isinstance(a, DocumentAttributeFilename)), None)
        if not name:
            ext = mimetypes.guess_extension(doc.mime_type or "") or ""
            name = f"document_{doc.id}{ext}"
        out.media_type = "document"
        out.document_id = int(doc.id)
        out.file_name = name
        out.mime_type = doc.mime_type
        out.size = int(doc.size)
    elif isinstance(media, MessageMediaPhoto) and media.photo is not None:
        photo = media.photo
        sizes = [getattr(s, "size", 0) or max(getattr(s, "sizes", [0]) or [0])
                 for s in getattr(photo, "sizes", [])]
        out.media_type = "photo"
        out.document_id = int(photo.id)
        out.file_name = f"photo_{msg.id}.jpg"
        out.mime_type = "image/jpeg"
        out.size = int(max(sizes)) if sizes else None
    elif media is not None:
        out.media_type = type(media).__name__.removeprefix("MessageMedia").lower() or "other"
    return out


class TelethonGateway:
    def __init__(self, settings: Settings, client: TelegramClient | None = None) -> None:
        self.settings = settings
        self.client = client or build_client(settings)

    async def connect(self) -> None:
        await self.client.connect()
        secure_session_file(self.settings)

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def is_authorized(self) -> bool:
        return bool(await self.client.is_user_authorized())

    async def resolve(self, ref: str | int) -> TgEntity:
        try:
            entity = await self.client.get_entity(ref)
        except errors.FloodWaitError as exc:
            raise FloodWaitError(exc.seconds) from exc
        except (ValueError, errors.RPCError) as exc:
            raise ChannelUnavailableError(f"Cannot access channel {ref!r}: {exc}") from exc
        title = getattr(entity, "title", None) or getattr(entity, "first_name", "") or str(ref)
        return TgEntity(id=int(entity.id), title=title, username=getattr(entity, "username", None))

    async def iter_messages(self, entity: TgEntity, *, min_id: int, limit: int | None,
                            documents_only: bool = False) -> AsyncIterator[TgMessage]:
        target: str | int = entity.username or entity.id
        # Server-side filter: busy chat groups are >90% text, so asking Telegram for documents
        # only avoids paging through hundreds of thousands of messages we would skip anyway.
        msg_filter = InputMessagesFilterDocument if documents_only else None
        try:
            async for msg in self.client.iter_messages(target, min_id=min_id, reverse=True,
                                                        limit=limit, filter=msg_filter):
                if getattr(msg, "action", None) is not None:
                    continue  # service messages (pins, joins, …)
                yield _to_tg_message(msg)
        except errors.FloodWaitError as exc:
            raise FloodWaitError(exc.seconds) from exc

    async def download(self, message: TgMessage, dest: Path,
                       progress: ProgressCb | None = None) -> None:
        try:
            await self.client.download_media(message.raw, file=str(dest),
                                              progress_callback=progress)
        except errors.FloodWaitError as exc:
            raise FloodWaitError(exc.seconds) from exc
        if not dest.exists():
            raise ChannelUnavailableError("Download produced no file")
