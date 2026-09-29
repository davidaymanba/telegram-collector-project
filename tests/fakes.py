"""In-memory stand-ins for Telegram and OpenAI."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.telegram.gateway import (
    FloodWaitError,
    ProgressCb,
    TgEntity,
    TgMessage,
)


def doc_msg(msg_id: int, name: str, content: bytes, *, document_id: int | None = None,
            caption: str = "") -> tuple[TgMessage, bytes]:
    return TgMessage(id=msg_id, date=datetime(2026, 9, 1, tzinfo=UTC), text=caption,
                     media_type="document", document_id=document_id or 10_000 + msg_id,
                     file_name=name, mime_type="application/pdf", size=len(content)), content


@dataclass
class FakeGateway:
    messages: list[TgMessage] = field(default_factory=list)
    contents: dict[int, bytes] = field(default_factory=dict)
    authorized: bool = True
    flood_on_iter_at: dict[int, int] = field(default_factory=dict)   # msg_id -> seconds (once)
    flood_on_download: dict[int, int] = field(default_factory=dict)  # msg_id -> seconds (once)
    fail_download: set[int] = field(default_factory=set)
    downloads: list[int] = field(default_factory=list)
    iter_calls: list[int] = field(default_factory=list)
    connected: bool = False

    def add(self, pair: tuple[TgMessage, bytes]) -> None:
        msg, content = pair
        self.messages.append(msg)
        self.contents[msg.id] = content

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def is_authorized(self) -> bool:
        return self.authorized

    async def resolve(self, ref: str | int) -> TgEntity:
        return TgEntity(id=4242, title="Fake channel", username=str(ref))

    async def iter_messages(self, entity: TgEntity, *, min_id: int, limit: int | None
                            ) -> AsyncIterator[TgMessage]:
        self.iter_calls.append(min_id)
        count = 0
        for msg in sorted(self.messages, key=lambda m: m.id):
            if msg.id <= min_id:
                continue
            if msg.id in self.flood_on_iter_at:
                raise FloodWaitError(self.flood_on_iter_at.pop(msg.id))
            if limit is not None and count >= limit:
                return
            count += 1
            yield msg

    async def download(self, message: TgMessage, dest: Path,
                       progress: ProgressCb | None = None) -> None:
        if message.id in self.flood_on_download:
            raise FloodWaitError(self.flood_on_download.pop(message.id))
        if message.id in self.fail_download:
            raise ConnectionError("network down")
        self.downloads.append(message.id)
        dest.write_bytes(self.contents[message.id])


class FakeSleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class FakeResponses:
    def __init__(self, payload: dict[str, Any] | str | Exception) -> None:
        self.payload = payload
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        if isinstance(self.payload, Exception):
            raise self.payload
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return SimpleNamespace(output_text=text)


class FakeOpenAI:
    def __init__(self, payload: dict[str, Any] | str | Exception) -> None:
        self.responses = FakeResponses(payload)
