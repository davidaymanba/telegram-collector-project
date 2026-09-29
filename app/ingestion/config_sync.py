"""Import YAML seed files into the database (the source of truth) and export them back."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config.loaders import ChannelConfig, SubjectConfig, dump_yaml
from app.database.enums import ChannelStatus
from app.database.models import Channel, Subject
from app.database.repositories import ChannelRepository, SubjectRepository


@dataclass(slots=True)
class ImportResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"created": self.created, "updated": self.updated, "unchanged": self.unchanged}


def import_subjects(session: Session, subjects: list[SubjectConfig]) -> ImportResult:
    repo = SubjectRepository(session)
    result = ImportResult()
    for cfg in subjects:
        obj = repo.get_by_code(cfg.code)
        if obj is None:
            repo.add(Subject(code=cfg.code, name_ar=cfg.name_ar, name_en=cfg.name_en,
                             keywords=cfg.keywords))
            result.created += 1
            continue
        changed = (obj.name_ar, obj.name_en, obj.keywords) != (cfg.name_ar, cfg.name_en,
                                                                cfg.keywords)
        if changed:
            obj.name_ar, obj.name_en, obj.keywords = cfg.name_ar, cfg.name_en, list(cfg.keywords)
            result.updated += 1
        else:
            result.unchanged += 1
    session.flush()
    return result


def import_channels(session: Session, channels: list[ChannelConfig]) -> ImportResult:
    repo = ChannelRepository(session)
    result = ImportResult()
    for cfg in channels:
        obj = None
        if cfg.telegram_id is not None:
            obj = repo.get_by_telegram_id(cfg.telegram_id)
        if obj is None and cfg.username:
            obj = repo.get_by_username(cfg.username)
        if obj is None:
            repo.add(Channel(
                name=cfg.name, username=cfg.username, telegram_id=cfg.telegram_id,
                enabled=cfg.enabled, last_message_id=0,
                status=ChannelStatus.IDLE if cfg.enabled else ChannelStatus.DISABLED,
            ))
            result.created += 1
            continue
        before = (obj.name, obj.username, obj.telegram_id, obj.enabled)
        obj.name = cfg.name
        obj.username = cfg.username or obj.username
        obj.telegram_id = cfg.telegram_id if cfg.telegram_id is not None else obj.telegram_id
        obj.enabled = cfg.enabled
        if (obj.name, obj.username, obj.telegram_id, obj.enabled) != before:
            result.updated += 1
        else:
            result.unchanged += 1
    session.flush()
    return result


def export_subjects(session: Session) -> str:
    data: dict[str, Any] = {"subjects": [
        {"code": s.code, "name_ar": s.name_ar, "name_en": s.name_en, "keywords": list(s.keywords)}
        for s in SubjectRepository(session).list_all()
    ]}
    return dump_yaml(data)


def export_channels(session: Session) -> str:
    items: list[dict[str, Any]] = []
    for c in ChannelRepository(session).list_all():
        item: dict[str, Any] = {"name": c.name}
        if c.username:
            item["username"] = c.username
        if c.telegram_id is not None:
            item["telegram_id"] = c.telegram_id
        item["enabled"] = c.enabled
        items.append(item)
    return dump_yaml({"channels": items})
