from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.config.loaders import parse_channels, parse_subjects
from app.database.enums import ClassificationStatus, FileStatus, ProcessingLogStatus, RunKind, RunTrigger
from app.database.models import Channel, Message, Subject
from app.database.repositories import (
    ChannelRepository,
    ClassificationRepository,
    FileFilters,
    FileRepository,
    MessageRepository,
    ProcessingLogRepository,
    RunRepository,
    SubjectRepository,
)
from app.database.session import get_engine
from app.ingestion.config_sync import export_channels, export_subjects, import_channels, import_subjects
from tests.conftest import make_file


def test_schema_is_utf8mb4(settings: Settings) -> None:
    with get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT TABLE_NAME, TABLE_COLLATION FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME <> 'alembic_version'"
        )).all()
        assert rows
        assert {c for _, c in rows} == {"utf8mb4_unicode_ci"}
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == "0001_initial"


def test_arabic_and_emoji_roundtrip(db: Session) -> None:
    ch = Channel(name="قناة 📚 الاختبار", username="rt_test", last_message_id=0)
    db.add(ch)
    db.commit()
    db.expire_all()
    assert ChannelRepository(db).get_by_username("RT_TEST").name == "قناة 📚 الاختبار"  # type: ignore[union-attr]


def test_channel_find(db: Session, channel: Channel) -> None:
    repo = ChannelRepository(db)
    channel.telegram_id = -100123
    db.commit()
    assert repo.find(str(channel.id)) is channel
    assert repo.find("@test_channel") is channel
    assert repo.find("-100123") is channel
    assert repo.find("قناة الاختبار") is channel
    assert repo.find("missing") is None


def test_message_unique_per_channel(db: Session, channel: Channel) -> None:
    now = datetime.now(UTC)
    db.add(Message(channel_id=channel.id, telegram_message_id=1, message_date=now,
                   telegram_metadata={}))
    db.commit()
    db.add(Message(channel_id=channel.id, telegram_message_id=1, message_date=now,
                   telegram_metadata={}))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert MessageRepository(db).get_by_telegram_id(channel.id, 1) is not None


def test_datetimes_are_utc_aware(db: Session, channel: Channel) -> None:
    db.expire_all()
    ch = ChannelRepository(db).get(channel.id)
    assert ch is not None and ch.created_at.tzinfo is not None


def test_file_dedup_lookups(db: Session, channel: Channel) -> None:
    repo = FileRepository(db)
    a = make_file(db, channel, None, name="a.pdf", msg_id=1)
    a.telegram_document_id = 999
    a.sha256 = "a" * 64
    dup = make_file(db, channel, None, name="b.pdf", msg_id=2, status=FileStatus.DUPLICATE)
    dup.telegram_document_id = 999
    dup.sha256 = "a" * 64
    db.commit()
    assert repo.find_canonical_by_document_id(999) is a
    assert repo.find_canonical_by_sha256("a" * 64) is a
    assert repo.find_canonical_by_sha256("a" * 64, exclude_id=a.id) is None
    assert repo.find_canonical_by_document_id(1) is None


def test_file_search_filters_sort_and_pagination(db: Session, channel: Channel) -> None:
    repo = FileRepository(db)
    files = [make_file(db, channel, None, name=f"محاضرة {i}.pdf", msg_id=i, caption="DB")
             for i in range(1, 8)]
    files[0].status = FileStatus.CLASSIFIED
    files[1].extension = "docx"
    files[2].created_at = datetime.now(UTC) - timedelta(days=10)
    db.commit()
    ClassificationRepository(db).upsert(files[0].id, status=ClassificationStatus.CLASSIFIED,
                                        subject_code="DB101", content_type="lecture",
                                        confidence=0.9, evidence=["x"], reason=None,
                                        classifier_version="rules-v1")
    db.commit()

    page = repo.search(FileFilters(), page=1, page_size=3)
    assert page.total == 7 and len(page.items) == 3 and page.pages == 3
    assert repo.search(FileFilters(q="محاضرة 3")).total == 1
    assert repo.search(FileFilters(status=[FileStatus.CLASSIFIED])).total == 1
    assert repo.search(FileFilters(subject_code="DB101", content_type="lecture")).total == 1
    assert repo.search(FileFilters(extension=".DOCX")).total == 1
    assert repo.search(FileFilters(date_to=datetime.now(UTC) - timedelta(days=5))).total == 1
    asc = repo.search(FileFilters(), sort="original_filename", order="asc", page_size=50)
    names = [f.original_filename for f in asc.items]
    assert names == sorted(names)
    assert repo.status_counts() == {"classified": 1, "downloaded": 6}
    assert set(repo.extensions()) == {"pdf", "docx"}


def test_classification_upsert_and_counts(db: Session, channel: Channel, subjects: list[Subject]) -> None:
    f = make_file(db, channel, None, name="x.pdf", msg_id=1)
    repo = ClassificationRepository(db)
    repo.upsert(f.id, status=ClassificationStatus.UNCLASSIFIED, subject_code=None,
                content_type=None, confidence=None, evidence=[], reason="r",
                classifier_version="rules-v1")
    obj = repo.upsert(f.id, status=ClassificationStatus.CLASSIFIED, subject_code="DB101",
                      content_type="summary", confidence=1.0, evidence=["m"], reason=None,
                      classifier_version="manual")
    db.commit()
    assert obj.id == repo.get_for_file(f.id).id  # type: ignore[union-attr]
    assert repo.counts_by("subject_code") == {"DB101": 1}
    assert SubjectRepository(db).counts_by_type() == {"DB101": {"summary": 1}}


def test_runs_and_logs(db: Session, channel: Channel) -> None:
    runs = RunRepository(db)
    run = runs.start(RunKind.COLLECT, RunTrigger.CLI, {"a": 1})
    f = make_file(db, channel, None, name="x.pdf", msg_id=1)
    ProcessingLogRepository(db).record(stage="download", status=ProcessingLogStatus.SUCCESS,
                                       file_id=f.id, run_id=run.id, message="ok")
    runs.finish(run, {"new": 3, "failed": 1}, metadata={"b": 2})
    db.commit()
    assert run.new_count == 3 and run.failed_count == 1 and run.status == "success"
    assert run.metadata_json == {"a": 1, "b": 2}
    assert run.duration_seconds is not None and run.duration_seconds >= 0
    assert len(ProcessingLogRepository(db).for_run(run.id)) == 1
    assert len(ProcessingLogRepository(db).for_file(f.id)) == 1
    stale = runs.start(RunKind.PROCESS, RunTrigger.LAUNCHD)
    assert runs.mark_stale_running() == 1
    assert stale.status == "aborted"


def test_cascade_delete_channel(db: Session, channel: Channel) -> None:
    make_file(db, channel, None, name="x.pdf", msg_id=1)
    ChannelRepository(db).delete(channel)
    db.commit()
    assert FileRepository(db).status_counts() == {}


def test_config_import_export_roundtrip(db: Session) -> None:
    subjects = parse_subjects({"subjects": [
        {"code": "DB101", "name_ar": "قواعد البيانات", "name_en": "Database", "keywords": ["sql"]},
    ]})
    assert import_subjects(db, subjects).as_dict() == {"created": 1, "updated": 0, "unchanged": 0}
    assert import_subjects(db, subjects).as_dict() == {"created": 0, "updated": 0, "unchanged": 1}
    subjects[0].keywords = ["sql", "erd"]
    assert import_subjects(db, subjects).updated == 1

    channels = parse_channels({"channels": [{"name": "A", "username": "chan_a"},
                                            {"name": "B", "telegram_id": -1001, "enabled": False}]})
    assert import_channels(db, channels).created == 2
    assert import_channels(db, channels).unchanged == 2
    db.commit()
    assert "قواعد البيانات" in export_subjects(db)
    exported = parse_channels(__import__("yaml").safe_load(export_channels(db)))
    assert {c.name for c in exported} == {"A", "B"}
