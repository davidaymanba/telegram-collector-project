from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config.loaders import SUBJECT_CODE_RE
from app.database.enums import CONTENT_TYPES, ChannelStatus, FileStatus, RunKind, RunTrigger

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageOut(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------- auth
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)


class MeOut(BaseModel):
    username: str
    csrf_token: str


# ---------------------------------------------------------------- channels
def clean_username(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip().removeprefix("https://t.me/").removeprefix("@").strip("/")
    if v and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,63}", v):
        raise ValueError("Invalid Telegram username")
    return v or None


def clean_keywords(v: list[str]) -> list[str]:
    out: dict[str, str] = {}
    for k in v:
        k = k.strip()[:100]
        if k:
            out.setdefault(k.casefold(), k)
    return list(out.values())


class ChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    username: str | None = Field(default=None, max_length=64)
    telegram_id: int | None = None
    enabled: bool = True

    @field_validator("username")
    @classmethod
    def _username(cls, v: str | None) -> str | None:
        return clean_username(v)


class ChannelPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    username: str | None = None
    telegram_id: int | None = None
    enabled: bool | None = None
    last_message_id: int | None = Field(default=None, ge=0)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str | None) -> str | None:
        return clean_username(v)


class ChannelOut(ORM):
    id: int
    telegram_id: int | None
    name: str
    username: str | None
    enabled: bool
    last_message_id: int
    last_run_at: datetime | None
    status: ChannelStatus
    last_error: str | None
    created_at: datetime
    file_count: int = 0


# ---------------------------------------------------------------- subjects
class SubjectIn(BaseModel):
    code: str
    name_ar: str = Field(min_length=1, max_length=255)
    name_en: str = Field(min_length=1, max_length=255)
    keywords: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        v = v.strip().upper()
        if not SUBJECT_CODE_RE.match(v):
            raise ValueError("Code must be 2–32 letters/digits/-/_ starting with a letter")
        return v

    @field_validator("keywords")
    @classmethod
    def _kw(cls, v: list[str]) -> list[str]:
        return clean_keywords(v)


class SubjectPatch(BaseModel):
    name_ar: str | None = Field(default=None, min_length=1, max_length=255)
    name_en: str | None = Field(default=None, min_length=1, max_length=255)
    keywords: list[str] | None = None

    @field_validator("keywords")
    @classmethod
    def _kw(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else clean_keywords(v)


class SubjectOut(ORM):
    id: int
    code: str
    name_ar: str
    name_en: str
    keywords: list[str]
    counts: dict[str, int] = Field(default_factory=dict)
    total: int = 0


# ---------------------------------------------------------------- files
class ClassificationOut(ORM):
    subject_code: str | None
    content_type: str | None
    confidence: float | None
    evidence: list[str]
    status: str
    reason: str | None
    classifier_version: str
    updated_at: datetime


class ChannelBrief(ORM):
    id: int
    name: str
    username: str | None


class MessageBrief(ORM):
    id: int
    telegram_message_id: int
    message_date: datetime
    caption: str | None
    media_type: str
    channel: ChannelBrief


class FileOut(ORM):
    id: int
    original_filename: str
    extension: str
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None
    status: FileStatus
    error_message: str | None
    telegram_document_id: int | None
    duplicate_of_file_id: int | None
    created_at: datetime
    updated_at: datetime
    message: MessageBrief
    classification: ClassificationOut | None


class LogOut(ORM):
    id: int
    stage: str
    status: str
    message: str | None
    error_message: str | None
    created_at: datetime
    run_id: int | None
    file_id: int | None


class FileDetailOut(FileOut):
    storage_path: str | None
    relative_path: str | None
    exists_on_disk: bool
    text_preview: str | None
    text_length: int
    telegram_link: str | None
    message_metadata: dict[str, Any]
    logs: list[LogOut]


class ManualClassifyIn(BaseModel):
    subject_code: str
    content_type: str

    @field_validator("content_type")
    @classmethod
    def _ctype(cls, v: str) -> str:
        if v not in CONTENT_TYPES:
            raise ValueError(f"content_type must be one of {', '.join(CONTENT_TYPES)}")
        return v


class FacetsOut(BaseModel):
    extensions: list[str]
    statuses: list[str]
    content_types: list[str]
    subjects: list[str]
    status_counts: dict[str, int]


# ---------------------------------------------------------------- messages
class MessageOut(ORM):
    id: int
    telegram_message_id: int
    message_date: datetime
    caption: str | None
    media_type: str
    file_name: str | None
    file_size: int | None
    channel: ChannelBrief
    file_id: int | None = None
    file_status: FileStatus | None = None


# ---------------------------------------------------------------- runs
class RunOut(ORM):
    id: int
    kind: RunKind
    trigger: RunTrigger
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    new_count: int
    duplicate_count: int
    classified_count: int
    unclassified_count: int
    failed_count: int
    unsupported_count: int
    metadata_json: dict[str, Any]


class RunDetailOut(RunOut):
    logs: list[LogOut]
    log_lines: list[dict[str, Any]]


# ---------------------------------------------------------------- jobs
class JobIn(BaseModel):
    kind: Literal["collect", "process", "reclassify"]
    channel: str | None = Field(default=None, max_length=255)
    limit: int | None = Field(default=None, ge=1, le=100_000)


class JobOut(BaseModel):
    id: str
    kind: str
    args: list[str]
    state: str
    created_at: datetime
    finished_at: datetime | None
    exit_code: int | None
    run_id: int | None
    progress: dict[str, Any]
    counters: dict[str, int]
    line_count: int


class LockOut(BaseModel):
    locked: bool
    holder: dict[str, Any] | None
    active_job: JobOut | None
