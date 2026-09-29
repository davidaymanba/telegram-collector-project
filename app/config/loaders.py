"""YAML seed files for channels and subjects.

The database is the source of truth; these files are only used for the initial import
(`import-config`) and for exporting the current state (`export-config`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

SUBJECT_CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,31}$")


class ConfigError(ValueError):
    """Raised when a YAML seed file is missing or malformed."""


class SubjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    name_ar: str = Field(min_length=1)
    name_en: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        value = value.strip().upper()
        if not SUBJECT_CODE_RE.match(value):
            raise ValueError("code must be 2-32 chars: letters, digits, '-' or '_'")
        return value

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, value: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for kw in value:
            kw = str(kw).strip()
            if kw and kw.casefold() not in seen:
                seen[kw.casefold()] = kw
        return list(seen.values())


class ChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    username: str | None = None
    telegram_id: int | None = None
    enabled: bool = True

    @field_validator("username")
    @classmethod
    def _username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().removeprefix("https://t.me/").removeprefix("@").strip("/")
        return value or None


class SubjectsFile(BaseModel):
    subjects: list[SubjectConfig] = Field(default_factory=list)


class ChannelsFile(BaseModel):
    channels: list[ChannelConfig] = Field(default_factory=list)


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc


def parse_subjects(data: Any, source: str = "<data>") -> list[SubjectConfig]:
    try:
        parsed = SubjectsFile.model_validate(data or {})
    except ValidationError as exc:
        raise ConfigError(f"Invalid subjects config in {source}: {exc}") from exc
    codes = [s.code for s in parsed.subjects]
    dupes = sorted({c for c in codes if codes.count(c) > 1})
    if dupes:
        raise ConfigError(f"Duplicate subject codes in {source}: {', '.join(dupes)}")
    return parsed.subjects


def parse_channels(data: Any, source: str = "<data>") -> list[ChannelConfig]:
    try:
        parsed = ChannelsFile.model_validate(data or {})
    except ValidationError as exc:
        raise ConfigError(f"Invalid channels config in {source}: {exc}") from exc
    for ch in parsed.channels:
        if not ch.username and ch.telegram_id is None:
            raise ConfigError(f"Channel '{ch.name}' needs a username or telegram_id ({source})")
    return parsed.channels


def load_subjects(path: Path) -> list[SubjectConfig]:
    return parse_subjects(_read_yaml(path), str(path))


def load_channels(path: Path) -> list[ChannelConfig]:
    return parse_channels(_read_yaml(path), str(path))


def dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
