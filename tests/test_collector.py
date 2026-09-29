from __future__ import annotations

import asyncio
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.enums import ChannelStatus, FileStatus, RunKind, RunTrigger
from app.database.models import Channel, CollectedFile, Message, ProcessingRun
from app.runtime.runs import tracked_run
from app.telegram.collector import Collector, RateLimiter
from app.telegram.gateway import FloodWaitError, NotAuthorizedError, TgMessage
from tests.fakes import FakeGateway, FakeSleeper, doc_msg


def run_collect(settings: Settings, db: Session, gw: FakeGateway, sleeper: FakeSleeper | None = None,
                **kw: object):
    collector = Collector(settings, db, gw, sleep=sleeper or FakeSleeper())
    return asyncio.run(collector.collect(**kw))  # type: ignore[arg-type]


def files(db: Session) -> list[CollectedFile]:
    db.expire_all()
    return list(db.scalars(select(CollectedFile).order_by(CollectedFile.id)))


def test_collects_new_files_atomically(settings: Settings, db: Session, channel: Channel) -> None:
    gw = FakeGateway()
    gw.add(doc_msg(1, "DB101 Lecture 1.pdf", b"%PDF-1 a", caption="محاضرة ١"))
    gw.add(doc_msg(2, "محاضرة ٢ - قواعد البيانات.pdf", b"%PDF-1 b"))
    summary = run_collect(settings, db, gw)

    assert not summary.errors
    fs = files(db)
    assert [f.status for f in fs] == [FileStatus.DOWNLOADED, FileStatus.DOWNLOADED]
    for f in fs:
        p = Path(f.storage_path or "")
        assert p.exists() and p.is_relative_to(settings.incoming_dir)
        assert len(f.sha256 or "") == 64
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert not list(settings.incoming_dir.glob("*.part"))
    assert fs[1].original_filename == "محاضرة ٢ - قواعد البيانات.pdf"
    db.refresh(channel)
    assert channel.last_message_id == 2
    assert channel.status == ChannelStatus.ACTIVE and channel.last_run_at is not None
    assert not gw.connected  # always disconnects


def test_incremental_from_last_message_id(settings: Settings, db: Session, channel: Channel) -> None:
    gw = FakeGateway()
    gw.add(doc_msg(1, "a.pdf", b"a"))
    run_collect(settings, db, gw)
    gw.add(doc_msg(5, "b.pdf", b"b"))
    run_collect(settings, db, gw)
    assert gw.iter_calls == [0, 1]
    assert gw.downloads == [1, 5]
    db.refresh(channel)
    assert channel.last_message_id == 5


def test_early_dedup_by_document_id_skips_download(settings: Settings, db: Session,
                                                   channel: Channel) -> None:
    gw = FakeGateway()
    gw.add(doc_msg(1, "a.pdf", b"same", document_id=777))
    gw.add(doc_msg(2, "a (forwarded).pdf", b"same", document_id=777))
    run_collect(settings, db, gw)
    a, b = files(db)
    assert gw.downloads == [1]  # second one never downloaded
    assert b.status == FileStatus.DUPLICATE and b.duplicate_of_file_id == a.id
    assert b.storage_path is None


def test_sha256_dedup_after_download(settings: Settings, db: Session, channel: Channel) -> None:
    gw = FakeGateway()
    gw.add(doc_msg(1, "a.pdf", b"identical bytes", document_id=1))
    gw.add(doc_msg(2, "renamed.pdf", b"identical bytes", document_id=2))
    run_collect(settings, db, gw)
    a, b = files(db)
    assert gw.downloads == [1, 2]
    assert b.status == FileStatus.DUPLICATE and b.duplicate_of_file_id == a.id
    assert b.sha256 == a.sha256
    assert len(list(settings.incoming_dir.iterdir())) == 1  # duplicate bytes discarded


def test_unsupported_recorded_without_download(settings: Settings, db: Session,
                                               channel: Channel) -> None:
    gw = FakeGateway()
    gw.add(doc_msg(1, "old.doc", b"x"))
    gw.add(doc_msg(2, "video.mp4", b"x"))
    run_collect(settings, db, gw)
    fs = files(db)
    assert [f.status for f in fs] == [FileStatus.UNSUPPORTED, FileStatus.UNSUPPORTED]
    assert "legacy Office" in (fs[0].error_message or "")
    assert gw.downloads == []
    db.refresh(channel)
    assert channel.last_message_id == 2


def test_text_messages_optional(settings: Settings, db: Session, channel: Channel,
                                monkeypatch: pytest.MonkeyPatch) -> None:
    gw = FakeGateway(messages=[TgMessage(id=1, date=datetime.now(UTC), text="hello")])
    run_collect(settings, db, gw)
    assert db.scalar(select(Message)) is None
    db.refresh(channel)
    assert channel.last_message_id == 1  # still advanced

    settings.telegram_collect_text_messages = True
    gw.messages.append(TgMessage(id=2, date=datetime.now(UTC), text="مرحبا"))
    run_collect(settings, db, gw)
    msg = db.scalar(select(Message))
    assert msg is not None and msg.caption == "مرحبا" and msg.media_type == "none"


def test_flood_wait_during_iteration_resumes(settings: Settings, db: Session,
                                             channel: Channel) -> None:
    gw = FakeGateway(flood_on_iter_at={2: 7})
    for i in (1, 2, 3):
        gw.add(doc_msg(i, f"{i}.pdf", f"c{i}".encode()))
    sleeper = FakeSleeper()
    run_collect(settings, db, gw, sleeper)
    assert 8 in sleeper.calls  # waited the requested seconds (+1)
    assert gw.iter_calls == [0, 1]  # resumed from the last handled message
    assert gw.downloads == [1, 2, 3]
    db.refresh(channel)
    assert channel.last_message_id == 3


def test_flood_wait_during_download_retries(settings: Settings, db: Session,
                                            channel: Channel) -> None:
    gw = FakeGateway(flood_on_download={1: 3})
    gw.add(doc_msg(1, "a.pdf", b"a"))
    sleeper = FakeSleeper()
    run_collect(settings, db, gw, sleeper)
    assert 4 in sleeper.calls
    assert files(db)[0].status == FileStatus.DOWNLOADED


def test_flood_wait_too_long_marks_channel_error(settings: Settings, db: Session,
                                                 channel: Channel) -> None:
    settings.telegram_flood_max_wait_seconds = 60
    gw = FakeGateway(flood_on_iter_at={1: 3600})
    gw.add(doc_msg(1, "a.pdf", b"a"))
    summary = run_collect(settings, db, gw)
    assert summary.errors and "FloodWait" in summary.errors[0]
    db.refresh(channel)
    assert channel.status == ChannelStatus.ERROR and channel.last_message_id == 0


def test_failed_download_stops_and_retries_next_run(settings: Settings, db: Session,
                                                    channel: Channel) -> None:
    gw = FakeGateway(fail_download={2})
    for i in (1, 2, 3):
        gw.add(doc_msg(i, f"{i}.pdf", f"c{i}".encode()))
    run_collect(settings, db, gw)
    db.refresh(channel)
    assert channel.last_message_id == 1  # not advanced past the failure
    assert [f.status for f in files(db)] == [FileStatus.DOWNLOADED, FileStatus.FAILED]

    gw.fail_download.clear()
    run_collect(settings, db, gw)
    db.refresh(channel)
    assert channel.last_message_id == 3
    assert [f.status for f in files(db)] == [FileStatus.DOWNLOADED] * 3
    assert len(files(db)) == 3  # the failed row was reused, not duplicated


def test_limit_and_single_channel(settings: Settings, db: Session, channel: Channel) -> None:
    other = Channel(name="other", username="other_chan", enabled=True, last_message_id=0)
    db.add(other)
    db.commit()
    gw = FakeGateway()
    for i in range(1, 6):
        gw.add(doc_msg(i, f"{i}.pdf", f"c{i}".encode()))
    summary = run_collect(settings, db, gw, channel_ref="test_channel", limit=2)
    assert [c.name for c in summary.channels] == [channel.name]
    db.refresh(channel)
    assert channel.last_message_id == 2


def test_disabled_channels_skipped(settings: Settings, db: Session, channel: Channel) -> None:
    channel.enabled = False
    db.commit()
    gw = FakeGateway()
    gw.add(doc_msg(1, "a.pdf", b"a"))
    summary = run_collect(settings, db, gw)
    assert summary.channels == [] and gw.downloads == []


def test_not_authorized(settings: Settings, db: Session, channel: Channel) -> None:
    gw = FakeGateway(authorized=False)
    with pytest.raises(NotAuthorizedError, match="telegram-login"):
        run_collect(settings, db, gw)
    assert not gw.connected


def test_tracked_run_counts(settings: Settings, db: Session, channel: Channel) -> None:
    gw = FakeGateway()
    gw.add(doc_msg(1, "a.pdf", b"a", document_id=1))
    gw.add(doc_msg(2, "b.pdf", b"a", document_id=1))
    gw.add(doc_msg(3, "c.ppt", b"x"))
    with tracked_run(settings, RunKind.COLLECT, RunTrigger.CLI) as run:
        asyncio.run(Collector(settings, db, gw, sleep=FakeSleeper(), run=run).collect())
    db.expire_all()
    row = db.get(ProcessingRun, run.run_id)
    assert row is not None and row.status == "success" and row.finished_at is not None
    assert (row.new_count, row.duplicate_count, row.unsupported_count) == (1, 1, 1)
    assert (settings.log_dir / "runs" / f"{run.run_id}.jsonl").exists()


def test_rate_limiter_spaces_requests() -> None:
    sleeper = FakeSleeper()
    limiter = RateLimiter(1.0, sleeper)

    async def go() -> None:
        await limiter.wait()
        await limiter.wait()

    asyncio.run(go())
    assert len(sleeper.calls) == 1 and 0 < sleeper.calls[0] <= 1.0


def test_flood_error_message() -> None:
    assert "30s" in str(FloodWaitError(30))


def test_download_is_confined_to_storage(settings: Settings, db: Session, channel: Channel) -> None:
    gw = FakeGateway()
    gw.add(doc_msg(1, "../../../../etc/evil.pdf", b"x"))
    run_collect(settings, db, gw)
    [f] = files(db)
    assert Path(f.storage_path or "").resolve().is_relative_to(settings.storage_root.resolve())
    assert os.path.basename(f.storage_path or "") == f"{channel.id}_1_evil.pdf"
