from __future__ import annotations

import io
import zipfile
from typing import Any

import yaml
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import Settings
from app.config.loaders import (
    ConfigError,
    load_channels,
    load_subjects,
    parse_channels,
    parse_subjects,
)
from app.ingestion.config_sync import (
    export_channels,
    export_subjects,
    import_channels,
    import_subjects,
)
from app.ingestion.seed import seed_demo
from app.processing.classifiers.openai_classifier import OpenAIClassifier
from app.runtime.lock import JobLock, LockBusyError
from app.web.deps import DB, SettingsDep, User

router = APIRouter(prefix="/settings", tags=["settings"])
MAX_UPLOAD = 1024 * 1024

SECRET_FIELDS = {"database_url", "test_database_url", "telegram_api_hash", "openai_api_key",
                 "session_secret", "dashboard_password"}
SECTIONS: dict[str, list[str]] = {
    "app": ["app_env", "log_level", "log_format", "log_dir"],
    "database": ["database_url", "test_database_url"],
    "telegram": ["telegram_api_id", "telegram_api_hash", "telegram_session_path",
                 "telegram_request_delay_seconds", "telegram_collect_text_messages",
                 "telegram_flood_max_retries", "telegram_flood_max_wait_seconds"],
    "storage": ["storage_root", "incoming_storage_dir", "processed_storage_dir",
                "unclassified_storage_dir", "texts_storage_dir", "lock_file_path",
                "channels_config_path", "subjects_config_path"],
    "ocr": ["ocr_enabled", "ocr_language", "ocr_max_pages", "tesseract_cmd",
            "min_pdf_text_chars"],
    "classification": ["ai_provider", "openai_api_key", "openai_model",
                       "max_classification_chars", "classification_min_confidence",
                       "classification_min_evidence_items"],
    "schedule": ["collect_interval_minutes", "process_interval_minutes"],
    "web": ["session_secret", "dashboard_username", "dashboard_password",
            "session_max_age_seconds", "login_max_attempts", "login_window_seconds"],
}


def masked_settings(settings: Settings) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for section, keys in SECTIONS.items():
        rows = []
        for key in keys:
            value = getattr(settings, key)
            if key in SECRET_FIELDS:
                configured = value is not None and bool(value.get_secret_value())
                rows.append({"key": key, "secret": True, "configured": configured, "value": None})
            else:
                rows.append({"key": key, "secret": False, "configured": value is not None,
                             "value": None if value is None else str(getattr(value, "value",
                                                                             value))})
        out[section] = rows
    return out


@router.get("")
def get_settings_view(_: User, settings: SettingsDep) -> dict[str, Any]:
    return {"sections": masked_settings(settings)}


@router.post("/seed-demo")
def seed(db: DB, _: User, settings: SettingsDep, reset: bool = False) -> dict[str, Any]:
    try:
        with JobLock(settings.lock_path, kind="seed", trigger="web"):
            result = seed_demo(db, settings, reset=reset)
            db.commit()
    except LockBusyError as exc:
        raise HTTPException(423, "Another job is running") from exc
    return result


async def _read_yaml(upload: UploadFile | None) -> Any:
    if upload is None:
        return None
    raw = await upload.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "File too large")
    try:
        return yaml.safe_load(raw.decode("utf-8")) or {}
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise HTTPException(422, f"Invalid YAML: {exc}") from exc


@router.post("/import-config")
async def import_config(
    db: DB, _: User, settings: SettingsDep,
    subjects: UploadFile | None = File(default=None),
    channels: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    """Import uploaded YAML files, or the configured seed files when nothing is uploaded."""
    out: dict[str, Any] = {}
    try:
        if subjects is None and channels is None:
            out["subjects"] = import_subjects(db, load_subjects(settings.subjects_config_path)
                                              ).as_dict()
            if settings.channels_config_path.exists():
                out["channels"] = import_channels(db, load_channels(settings.channels_config_path)
                                                  ).as_dict()
        else:
            if (data := await _read_yaml(subjects)) is not None:
                out["subjects"] = import_subjects(db, parse_subjects(data, "upload")).as_dict()
            if (data := await _read_yaml(channels)) is not None:
                out["channels"] = import_channels(db, parse_channels(data, "upload")).as_dict()
    except ConfigError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    return out


@router.get("/export-config")
def export_config(db: DB, _: User) -> Response:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("subjects.yaml", export_subjects(db))
        zf.writestr("channels.yaml", export_channels(db))
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="tuc-config.zip"'})


@router.post("/test-openai")
def test_openai(_: User, settings: SettingsDep) -> dict[str, Any]:
    if not settings.openai_configured:
        return {"ok": False, "message": "TUC_OPENAI_API_KEY is not configured"}
    try:
        reply = OpenAIClassifier(settings).ping()
    except Exception as exc:
        return {"ok": False, "message": f"{type(exc).__name__}: {str(exc)[:300]}"}
    return {"ok": True, "message": f"Connected · {settings.openai_model} replied “{reply[:40]}”"}
