"""A thin, testable boundary around Telegram.

The collector talks to `TelegramGateway`; production uses `TelethonGateway`, tests use a fake.
Messages are normalised into `TgMessage` so the collector never touches Telethon types.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


class TelegramError(RuntimeError):
    pass


class NotAuthorizedError(TelegramError):
    pass


class CredentialsMissingError(TelegramError):
    pass


class ChannelUnavailableError(TelegramError):
    pass


class FloodWaitError(TelegramError):
    def __init__(self, seconds: int) -> None:
        self.seconds = int(seconds)
        super().__init__(f"Telegram asked us to wait {self.seconds}s (FloodWait)")


@dataclass(slots=True)
class TgEntity:
    id: int
    title: str
    username: str | None = None


@dataclass(slots=True)
class TgMessage:
    id: int
    date: datetime
    text: str = ""
    media_type: str = "none"          # none | document | photo | other
    document_id: int | None = None    # Telegram document.id / photo.id
    file_name: str | None = None
    mime_type: str | None = None
    size: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: Any = None                   # the original Telethon message (needed for download)


ProgressCb = Callable[[int, int], None]


class TelegramGateway(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def is_authorized(self) -> bool: ...
    async def resolve(self, ref: str | int) -> TgEntity: ...
    def iter_messages(self, entity: TgEntity, *, min_id: int, limit: int | None,
                      documents_only: bool = False) -> AsyncIterator[TgMessage]: ...
    async def download(self, message: TgMessage, dest: Path,
                       progress: ProgressCb | None = None) -> None: ...
