from __future__ import annotations

from pathlib import Path

import pytest

from app.config.loaders import (
    ConfigError,
    load_channels,
    load_subjects,
    parse_channels,
    parse_subjects,
)
from app.config.settings import PROJECT_ROOT, AIProvider, Settings


def test_settings_resolve_relative_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUC_STORAGE_ROOT", "data/store")
    monkeypatch.delenv("TUC_INCOMING_STORAGE_DIR", raising=False)
    monkeypatch.delenv("TUC_LOCK_FILE_PATH", raising=False)
    s = Settings(_env_file=None)
    assert s.storage_root == PROJECT_ROOT / "data/store"
    assert s.incoming_dir == PROJECT_ROOT / "data/store/incoming"
    assert s.lock_path == PROJECT_ROOT / "data/store/collector.lock"


def test_settings_types_and_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUC_AI_PROVIDER", "openai")
    monkeypatch.setenv("TUC_OCR_MAX_PAGES", "7")
    monkeypatch.setenv("TUC_TELEGRAM_API_ID", "")
    monkeypatch.setenv("TUC_OPENAI_API_KEY", "")
    monkeypatch.setenv("TUC_TESSERACT_CMD", "")
    monkeypatch.setenv("DASHBOARD_USERNAME", "boss")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "pw")
    s = Settings(_env_file=None)
    assert s.ai_provider is AIProvider.OPENAI
    assert s.ocr_max_pages == 7
    assert s.telegram_api_id is None
    assert s.openai_api_key is None and not s.openai_configured
    assert s.tesseract_cmd is None
    assert s.dashboard_username == "boss"
    assert s.dashboard_password is not None
    assert s.dashboard_password.get_secret_value() == "pw"
    assert "pw" not in repr(s)


def test_settings_session_file_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUC_TELEGRAM_SESSION_PATH", "/tmp/x/tuc")
    s = Settings(_env_file=None)
    assert s.telegram_session_file == Path("/tmp/x/tuc.session")


def test_settings_log_format_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUC_LOG_FORMAT", "auto")
    monkeypatch.setenv("TUC_APP_ENV", "production")
    assert Settings(_env_file=None).effective_log_format == "json"
    monkeypatch.setenv("TUC_APP_ENV", "development")
    assert Settings(_env_file=None).effective_log_format == "console"


def test_repo_seed_subjects_are_valid() -> None:
    subjects = load_subjects(PROJECT_ROOT / "config" / "subjects.yaml")
    codes = [s.code for s in subjects]
    assert "DB101" in codes and "CS101" in codes
    db = next(s for s in subjects if s.code == "DB101")
    assert db.name_ar == "قواعد البيانات"
    assert "ERD" in db.keywords


def test_repo_seed_channels_are_valid() -> None:
    channels = load_channels(PROJECT_ROOT / "config" / "channels.yaml")
    assert channels and all(c.username or c.telegram_id for c in channels)


def test_subject_code_normalised_and_keywords_deduped() -> None:
    [s] = parse_subjects({"subjects": [{"code": " db101 ", "name_ar": "أ", "name_en": "A",
                                        "keywords": ["SQL", "sql", " ", "ERD"]}]})
    assert s.code == "DB101"
    assert s.keywords == ["SQL", "ERD"]


@pytest.mark.parametrize("data, match", [
    ({"subjects": [{"code": "A", "name_ar": "x", "name_en": "y"}]}, "code"),
    ({"subjects": [{"code": "AB1", "name_ar": "x", "name_en": "y"},
                   {"code": "ab1", "name_ar": "x", "name_en": "y"}]}, "Duplicate"),
    ({"subjects": [{"code": "AB1", "name_ar": "x", "name_en": "y", "extra": 1}]}, "extra"),
    ({"subjects": [{"code": "AB1", "name_en": "y"}]}, "name_ar"),
])
def test_invalid_subjects(data: object, match: str) -> None:
    with pytest.raises(ConfigError, match=match):
        parse_subjects(data)


def test_channels_username_normalised() -> None:
    [c] = parse_channels({"channels": [{"name": "X", "username": "https://t.me/cs_batch/"}]})
    assert c.username == "cs_batch"
    [c] = parse_channels({"channels": [{"name": "X", "username": "@cs_batch"}]})
    assert c.username == "cs_batch"


def test_channel_requires_identifier() -> None:
    with pytest.raises(ConfigError, match="username or telegram_id"):
        parse_channels({"channels": [{"name": "X"}]})


def test_missing_and_invalid_yaml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_subjects(tmp_path / "nope.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("subjects: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_subjects(bad)
