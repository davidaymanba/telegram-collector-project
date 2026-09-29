"""Test fixtures. Tests run against a real MySQL database whose name MUST end in `_test`."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect, make_url, text
from sqlalchemy.orm import Session

from app.config.settings import Settings, reset_settings_cache
from app.database.enums import FileStatus
from app.database.models import Channel, CollectedFile, Message, Subject
from app.database.session import get_sessionmaker, make_engine, reset_engine

TEST_PASSWORD = "correct horse battery staple"


def _test_database_url() -> str:
    configured = Settings().test_database_url
    url = os.environ.get("TUC_TEST_DATABASE_URL") or (
        configured.get_secret_value() if configured else None
    )
    if not url:
        pytest.exit("TUC_TEST_DATABASE_URL is not set (see .env.example)", returncode=2)
    name = make_url(url).database or ""
    if not name.endswith("_test"):
        pytest.exit(f"Refusing to run tests: database '{name}' does not end with '_test'. "
                    "Tests drop and truncate tables.", returncode=2)
    return url


TEST_DB_URL = _test_database_url()


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    """Drop everything, then build the schema through the real Alembic migration."""
    from app.database.migrate import upgrade_head

    engine = make_engine(TEST_DB_URL)
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in inspect(conn).get_table_names():
            conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    engine.dispose()
    upgrade_head(TEST_DB_URL)
    yield


def _truncate_all() -> None:
    engine = make_engine(TEST_DB_URL)
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in inspect(conn).get_table_names():
            if table != "alembic_version":
                conn.execute(text(f"TRUNCATE TABLE `{table}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    engine.dispose()


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Isolated settings: test DB, temp storage, AI off. Also exported as env vars so
    subprocesses (web jobs, CLI) see the same configuration."""
    storage = tmp_path / "storage"
    env = {
        "TUC_APP_ENV": "test",
        "TUC_DATABASE_URL": TEST_DB_URL,
        "TUC_STORAGE_ROOT": str(storage),
        "TUC_INCOMING_STORAGE_DIR": str(storage / "incoming"),
        "TUC_PROCESSED_STORAGE_DIR": str(storage / "processed"),
        "TUC_UNCLASSIFIED_STORAGE_DIR": str(storage / "unclassified"),
        "TUC_TEXTS_STORAGE_DIR": str(storage / "texts"),
        "TUC_LOCK_FILE_PATH": str(storage / "collector.lock"),
        "TUC_LOG_DIR": str(tmp_path / "logs"),
        "TUC_LOG_FORMAT": "console",
        "TUC_TELEGRAM_SESSION_PATH": str(tmp_path / "tg" / "test"),
        "TUC_TELEGRAM_REQUEST_DELAY_SECONDS": "0",
        "TUC_TELEGRAM_API_ID": "12345",
        "TUC_TELEGRAM_API_HASH": "0123456789abcdef0123456789abcdef",
        "TUC_AI_PROVIDER": "none",
        "TUC_OPENAI_API_KEY": "",
        "TUC_SESSION_SECRET": "test-secret-" + "x" * 40,
        "TUC_SUBJECTS_CONFIG_PATH": str(Path(__file__).parents[1] / "config" / "subjects.yaml"),
        "TUC_CHANNELS_CONFIG_PATH": str(Path(__file__).parents[1] / "config" / "channels.yaml"),
        "DASHBOARD_USERNAME": "admin",
        "DASHBOARD_PASSWORD": TEST_PASSWORD,
        "TUC_MIN_PDF_TEXT_CHARS": "20",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()
    reset_engine()
    from app.config import get_settings

    s = get_settings()
    yield s
    reset_engine()
    reset_settings_cache()
    _truncate_all()


@pytest.fixture
def db(settings: Settings) -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def subjects(db: Session) -> list[Subject]:
    items = [
        Subject(code="DB101", name_ar="قواعد البيانات", name_en="Database",
                keywords=["database", "sql", "قواعد بيانات", "ERD"]),
        Subject(code="CS101", name_ar="مقدمة علوم الحاسب", name_en="Introduction to Computer Science",
                keywords=["intro to cs", "مقدمة حاسب", "algorithms"]),
    ]
    db.add_all(items)
    db.commit()
    return items


@pytest.fixture
def channel(db: Session) -> Channel:
    ch = Channel(name="قناة الاختبار", username="test_channel", enabled=True, last_message_id=0)
    db.add(ch)
    db.commit()
    return ch


def make_file(db: Session, channel: Channel, path: Path | None, *, name: str, msg_id: int,
              caption: str | None = None, status: FileStatus = FileStatus.DOWNLOADED,
              ) -> CollectedFile:
    msg = Message(channel_id=channel.id, telegram_message_id=msg_id,
                  message_date=datetime.now(UTC), caption=caption, media_type="document",
                  file_name=name, telegram_metadata={})
    db.add(msg)
    db.flush()
    ext = name.rsplit(".", 1)[-1].lower()
    f = CollectedFile(message_id=msg.id, original_filename=name, extension=ext,
                      storage_path=str(path) if path else None, status=status,
                      size_bytes=path.stat().st_size if path and path.exists() else None)
    db.add(f)
    db.commit()
    return f
