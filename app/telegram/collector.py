"""Collect files from enabled Telegram channels into `storage/incoming/`.

Guarantees:
- reads oldest → newest from each channel's `last_message_id` and advances it after every
  message that was handled successfully (a crash never loses or repeats work);
- duplicates are caught *before* downloading via Telegram's document id, and again after
  downloading via SHA-256;
- downloads are atomic (`.part` then rename) and confined to the storage root;
- FloodWait is honoured (sleep the requested time, then resume from the last good message).
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from app.config import Settings
from app.database.enums import ChannelStatus, FileStatus, ProcessingLogStatus
from app.database.models import Channel, CollectedFile, Message
from app.database.repositories import (
    ChannelRepository,
    FileRepository,
    MessageRepository,
    ProcessingLogRepository,
)
from app.logging import get_logger
from app.runtime.runs import RunContext
from app.storage.paths import (
    SUPPORTED_EXTENSIONS,
    StorageLayout,
    move_file,
    nfc,
    safe_filename,
    sha256_file,
    split_extension,
)
from app.telegram.gateway import (
    FloodWaitError,
    NotAuthorizedError,
    TelegramError,
    TelegramGateway,
    TgEntity,
    TgMessage,
)

log = get_logger("tuc.collect")
T = TypeVar("T")
Sleeper = Callable[[float], Awaitable[None]]


class RateLimiter:
    """Ensures at least `interval` seconds between Telegram requests."""

    def __init__(self, interval: float, sleep: Sleeper = asyncio.sleep) -> None:
        self.interval = interval
        self._sleep = sleep
        self._last = 0.0

    async def wait(self) -> None:
        if self.interval <= 0:
            return
        delta = time.monotonic() - self._last
        if delta < self.interval:
            await self._sleep(self.interval - delta)
        self._last = time.monotonic()


@dataclass(slots=True)
class ChannelResult:
    channel_id: int
    name: str
    messages: int = 0
    error: str | None = None


@dataclass(slots=True)
class CollectSummary:
    channels: list[ChannelResult] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        return [f"{c.name}: {c.error}" for c in self.channels if c.error]


class Collector:
    def __init__(self, settings: Settings, session: Session, gateway: TelegramGateway, *,
                 sleep: Sleeper = asyncio.sleep, run: RunContext | None = None) -> None:
        self.settings = settings
        self.session = session
        self.gw = gateway
        self.sleep = sleep
        self.run = run
        self.layout = StorageLayout(settings)
        self.layout.ensure()
        self.channels = ChannelRepository(session)
        self.messages = MessageRepository(session)
        self.files = FileRepository(session)
        self.logs = ProcessingLogRepository(session)
        self.rate = RateLimiter(settings.telegram_request_delay_seconds, sleep)
        # Nothing but documents is wanted → let Telegram filter server-side.
        self.documents_only = (not settings.telegram_collect_photos
                               and not settings.telegram_collect_text_messages)

    # ------------------------------------------------------------------ utils
    def _bump(self, key: str) -> None:
        if self.run:
            self.run.bump(key)

    async def _with_flood_retry(self, what: str, fn: Callable[[], Awaitable[T]]) -> T:
        attempts = 0
        while True:
            await self.rate.wait()
            try:
                return await fn()
            except FloodWaitError as exc:
                attempts += 1
                if (attempts > self.settings.telegram_flood_max_retries
                        or exc.seconds > self.settings.telegram_flood_max_wait_seconds):
                    raise
                log.warning("flood_wait", action=what, seconds=exc.seconds, attempt=attempts)
                await self.sleep(exc.seconds + 1)

    def _record(self, f: CollectedFile, stage: str, status: ProcessingLogStatus,
                message: str | None = None, error: str | None = None) -> None:
        self.logs.record(stage=stage, status=status, file_id=f.id,
                         run_id=self.run.run_id if self.run else None,
                         message=message, error=error)

    # ------------------------------------------------------------------ public
    async def collect(self, channel_ref: str | None = None, limit: int | None = None
                      ) -> CollectSummary:
        if channel_ref:
            ch = self.channels.find(channel_ref)
            if ch is None:
                raise TelegramError(f"Channel not found in database: {channel_ref}")
            targets = [ch]
        else:
            targets = list(self.channels.list_enabled())
        summary = CollectSummary()
        if not targets:
            log.warning("no_enabled_channels")
            return summary

        await self.gw.connect()
        try:
            if not await self.gw.is_authorized():
                raise NotAuthorizedError(
                    "Telegram session is not authorized. Run: python -m app.cli telegram-login"
                )
            for index, ch in enumerate(targets, start=1):
                result = ChannelResult(ch.id, ch.name)
                summary.channels.append(result)
                log.info("channel_started", channel=ch.name, last_message_id=ch.last_message_id,
                         index=index, total=len(targets))
                try:
                    result.messages = await self.collect_channel(ch, limit)
                    ch.status = ChannelStatus.ACTIVE
                    ch.last_error = None
                except NotAuthorizedError:
                    raise
                except Exception as exc:
                    self.session.rollback()
                    ch = self.channels.get(result.channel_id) or ch
                    result.error = f"{type(exc).__name__}: {exc}"[:900]
                    ch.status = ChannelStatus.ERROR
                    ch.last_error = result.error
                    log.error("channel_failed", channel=ch.name, error=result.error)
                ch.last_run_at = datetime.now(UTC)
                self.session.commit()
                log.info("channel_finished", channel=ch.name, messages=result.messages,
                         last_message_id=ch.last_message_id)
        finally:
            await self.gw.disconnect()
        if self.run and summary.errors:
            self.run.metadata["channel_errors"] = summary.errors
        return summary

    async def collect_channel(self, ch: Channel, limit: int | None) -> int:
        ref: str | int = ch.username or ch.telegram_id or ch.name
        entity: TgEntity = await self._with_flood_retry("resolve", lambda: self.gw.resolve(ref))
        if ch.telegram_id is None:
            ch.telegram_id = entity.id
            self.session.commit()

        handled = 0
        flood_attempts = 0
        while True:
            remaining = None if limit is None else limit - handled
            if remaining is not None and remaining <= 0:
                break
            try:
                await self.rate.wait()
                async for msg in self.gw.iter_messages(entity, min_id=ch.last_message_id,
                                                       limit=remaining,
                                                       documents_only=self.documents_only):
                    if msg.id <= ch.last_message_id:
                        continue
                    if not await self.handle_message(ch, msg):
                        return handled  # stop here; next run retries this message
                    ch.last_message_id = msg.id
                    self.session.commit()
                    handled += 1
                    if self.run:
                        self.run.progress(handled, limit, channel=ch.name, message_id=msg.id)
                break
            except FloodWaitError as exc:
                flood_attempts += 1
                if (flood_attempts > self.settings.telegram_flood_max_retries
                        or exc.seconds > self.settings.telegram_flood_max_wait_seconds):
                    raise
                log.warning("flood_wait", action="iter_messages", seconds=exc.seconds,
                            resume_from=ch.last_message_id)
                await self.sleep(exc.seconds + 1)
        return handled

    # ------------------------------------------------------------------ messages
    def _store_message(self, ch: Channel, msg: TgMessage) -> Message:
        existing = self.messages.get_by_telegram_id(ch.id, msg.id)
        if existing is not None:
            return existing
        meta: dict[str, Any] = {k: v for k, v in msg.metadata.items() if v is not None}
        if msg.mime_type:
            meta["mime_type"] = msg.mime_type
        if msg.document_id:
            meta["document_id"] = str(msg.document_id)
        return self.messages.add(Message(
            channel_id=ch.id, telegram_message_id=msg.id, message_date=msg.date,
            caption=nfc(msg.text) if msg.text else None, media_type=msg.media_type,
            file_name=nfc(msg.file_name) if msg.file_name else None, file_size=msg.size,
            telegram_metadata=meta,
        ))

    async def handle_message(self, ch: Channel, msg: TgMessage) -> bool:
        """Returns False when the message must be retried on the next run."""
        if msg.media_type == "photo" and not self.settings.telegram_collect_photos:
            return True
        if msg.media_type not in ("document", "photo"):
            if msg.media_type == "none" and not self.settings.telegram_collect_text_messages:
                return True
            self._store_message(ch, msg)
            return True

        message = self._store_message(ch, msg)
        f = self.files.get_by_message(message.id)
        if f is not None and f.status != FileStatus.FAILED:
            return True  # already handled in an earlier run

        original = nfc(msg.file_name or f"file_{msg.id}")
        _, ext = split_extension(safe_filename(original))
        if f is None:
            f = self.files.add(CollectedFile(
                message_id=message.id, telegram_document_id=msg.document_id,
                original_filename=original[:512], mime_type=msg.mime_type, extension=ext,
                size_bytes=msg.size, status=FileStatus.DISCOVERED,
            ))

        if ext not in SUPPORTED_EXTENSIONS:
            f.status = FileStatus.UNSUPPORTED
            f.error_message = (f"Unsupported file type '.{ext}'" if ext else "File has no extension")
            if ext in {"doc", "ppt"}:
                f.error_message += " — legacy Office format; convert to .docx/.pptx or PDF"
            self._record(f, "collect", ProcessingLogStatus.SKIPPED, f.error_message)
            self._bump("unsupported")
            log.info("file_unsupported", file=original, ext=ext)
            return True

        if msg.document_id is not None:
            canonical = self.files.find_canonical_by_document_id(msg.document_id)
            if canonical is not None and canonical.id != f.id:
                self._mark_duplicate(f, canonical, "telegram document id")
                return True

        return await self._download(ch, msg, f)

    def _mark_duplicate(self, f: CollectedFile, canonical: CollectedFile, how: str) -> None:
        f.status = FileStatus.DUPLICATE
        f.duplicate_of_file_id = canonical.id
        f.error_message = None
        self._record(f, "dedup", ProcessingLogStatus.SKIPPED,
                     f"Duplicate of #{canonical.id} by {how}")
        self._bump("duplicate")
        log.info("file_duplicate", file=f.original_filename, duplicate_of=canonical.id, by=how)

    async def _download(self, ch: Channel, msg: TgMessage, f: CollectedFile) -> bool:
        final = self.layout.incoming_path(f"{ch.id}_{msg.id}", f.original_filename)
        part = final.with_name(final.name + ".part")
        part.unlink(missing_ok=True)
        log.info("download_started", file=f.original_filename, size=msg.size)
        try:
            await self._with_flood_retry("download", lambda: self.gw.download(msg, part))
            sha = sha256_file(part)
        except Exception as exc:
            part.unlink(missing_ok=True)
            f.status = FileStatus.FAILED
            f.error_message = f"Download failed: {type(exc).__name__}: {exc}"[:2000]
            self._record(f, "download", ProcessingLogStatus.FAILED, error=f.error_message)
            self._bump("failed")
            self.session.commit()
            log.error("download_failed", file=f.original_filename, error=str(exc))
            return False

        f.sha256 = sha
        f.size_bytes = part.stat().st_size
        canonical = self.files.find_canonical_by_sha256(sha, exclude_id=f.id)
        if canonical is not None:
            part.unlink(missing_ok=True)
            self._mark_duplicate(f, canonical, "sha256")
            return True

        stored = move_file(part, final)
        os.chmod(stored, 0o600)
        f.storage_path = str(stored)
        f.status = FileStatus.DOWNLOADED
        f.error_message = None
        self._record(f, "download", ProcessingLogStatus.SUCCESS,
                     f"{f.size_bytes} bytes · sha256 {sha[:12]}")
        self._bump("new")
        log.info("download_finished", file=f.original_filename, bytes=f.size_bytes)
        return True
