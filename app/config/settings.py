"""Application settings, loaded from environment variables and the project `.env` file.

Every path setting may be relative; relative paths resolve against the project root so
the CLI, the web server and launchd jobs all agree regardless of working directory.
"""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = Path(os.environ.get("TUC_ENV_FILE", PROJECT_ROOT / ".env"))


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class AIProvider(StrEnum):
    NONE = "none"
    OPENAI = "openai"


def resolve_path(value: Path | str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TUC_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- app ---------------------------------------------------------------
    app_env: AppEnv = AppEnv.DEVELOPMENT
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["auto", "json", "console"] = "auto"
    log_dir: Path = Path("logs")

    # --- database ----------------------------------------------------------
    database_url: SecretStr = SecretStr(
        "mysql+pymysql://tuc:tuc_password@127.0.0.1:3306/tuc?charset=utf8mb4"
    )
    test_database_url: SecretStr | None = None

    # --- telegram ----------------------------------------------------------
    telegram_api_id: int | None = None
    telegram_api_hash: SecretStr | None = None
    telegram_session_path: Path = Path("storage/telegram/tuc")
    telegram_request_delay_seconds: float = Field(default=1.0, ge=0)
    telegram_collect_text_messages: bool = False
    telegram_collect_photos: bool = True
    telegram_flood_max_retries: int = Field(default=3, ge=0)
    telegram_flood_max_wait_seconds: int = Field(default=900, ge=1)

    # --- seed configuration -----------------------------------------------
    channels_config_path: Path = Path("config/channels.yaml")
    subjects_config_path: Path = Path("config/subjects.yaml")

    # --- storage -----------------------------------------------------------
    storage_root: Path = Path("storage")
    incoming_storage_dir: Path | None = None
    processed_storage_dir: Path | None = None
    unclassified_storage_dir: Path | None = None
    texts_storage_dir: Path | None = None
    lock_file_path: Path | None = None

    # --- OCR ---------------------------------------------------------------
    ocr_enabled: bool = True
    ocr_language: str = "ara+eng"
    ocr_max_pages: int = Field(default=15, ge=1)
    tesseract_cmd: str | None = None
    min_pdf_text_chars: int = Field(default=200, ge=0)

    # --- classification ----------------------------------------------------
    ai_provider: AIProvider = AIProvider.NONE
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini"
    max_classification_chars: int = Field(default=6000, ge=100)
    classification_min_confidence: float = Field(default=0.7, ge=0, le=1)
    classification_min_evidence_items: int = Field(default=1, ge=0)

    # --- scheduling --------------------------------------------------------
    collect_interval_minutes: int = Field(default=30, ge=1)
    process_interval_minutes: int = Field(default=15, ge=1)

    # --- web ---------------------------------------------------------------
    session_secret: SecretStr | None = None
    session_max_age_seconds: int = 60 * 60 * 12
    dashboard_username: str = Field(
        default="admin",
        validation_alias=AliasChoices("DASHBOARD_USERNAME", "TUC_DASHBOARD_USERNAME"),
    )
    dashboard_password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DASHBOARD_PASSWORD", "TUC_DASHBOARD_PASSWORD"),
    )
    login_max_attempts: int = 5
    login_window_seconds: int = 300

    @field_validator("tesseract_cmd", "telegram_api_id", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("openai_api_key", "telegram_api_hash", "session_secret",
                     "dashboard_password", "test_database_url", mode="before")
    @classmethod
    def _empty_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _resolve_paths(self) -> Settings:
        self.log_dir = resolve_path(self.log_dir)
        self.telegram_session_path = resolve_path(self.telegram_session_path)
        self.channels_config_path = resolve_path(self.channels_config_path)
        self.subjects_config_path = resolve_path(self.subjects_config_path)
        self.storage_root = resolve_path(self.storage_root)
        root = self.storage_root
        self.incoming_storage_dir = resolve_path(self.incoming_storage_dir or root / "incoming")
        self.processed_storage_dir = resolve_path(self.processed_storage_dir or root / "processed")
        self.unclassified_storage_dir = resolve_path(
            self.unclassified_storage_dir or root / "unclassified"
        )
        self.texts_storage_dir = resolve_path(self.texts_storage_dir or root / "texts")
        self.lock_file_path = resolve_path(self.lock_file_path or root / "collector.lock")
        return self

    # --- convenience -------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION

    @property
    def effective_log_format(self) -> Literal["json", "console"]:
        if self.log_format == "auto":
            return "json" if self.is_production else "console"
        return self.log_format

    @property
    def telegram_session_file(self) -> Path:
        """Telethon appends `.session` to the session name."""
        path = self.telegram_session_path
        return path if path.suffix == ".session" else path.with_name(path.name + ".session")

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_api_id and self.telegram_api_hash)

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.get_secret_value())

    # Typed non-optional accessors for the derived storage paths.
    @property
    def incoming_dir(self) -> Path:
        assert self.incoming_storage_dir is not None
        return self.incoming_storage_dir

    @property
    def processed_dir(self) -> Path:
        assert self.processed_storage_dir is not None
        return self.processed_storage_dir

    @property
    def unclassified_dir(self) -> Path:
        assert self.unclassified_storage_dir is not None
        return self.unclassified_storage_dir

    @property
    def texts_dir(self) -> Path:
        assert self.texts_storage_dir is not None
        return self.texts_storage_dir

    @property
    def lock_path(self) -> Path:
        assert self.lock_file_path is not None
        return self.lock_file_path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
