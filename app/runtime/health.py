from __future__ import annotations

import shutil
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import text

from app.config import PROJECT_ROOT, AIProvider, Settings
from app.runtime.lock import lock_status
from app.runtime.tesseract import find_tesseract, missing_languages, tesseract_version

Level = Literal["ok", "warn", "fail"]


@dataclass(slots=True)
class Check:
    key: str
    status: Level
    detail: str
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_mysql(settings: Settings) -> Check:
    from app.database.session import get_engine

    try:
        with get_engine().connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
            row = conn.execute(text(
                "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
                "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = DATABASE()"
            )).one()
            has_schema = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'alembic_version'"
            )).scalar()
    except Exception as exc:
        return Check("mysql", "fail", f"Cannot connect: {type(exc).__name__}: {str(exc)[:200]}")
    charset, collation = row
    data = {"version": version, "charset": charset, "collation": collation,
            "migrated": bool(has_schema)}
    if charset != "utf8mb4":
        return Check("mysql", "fail", f"Database charset is {charset}, expected utf8mb4", data)
    if not has_schema:
        return Check("mysql", "warn", "Connected, but schema missing — run init-db", data)
    return Check("mysql", "ok", f"MySQL {version} · {charset}/{collation}", data)


def check_tesseract(settings: Settings) -> Check:
    if not settings.ocr_enabled:
        return Check("tesseract", "warn", "OCR disabled (TUC_OCR_ENABLED=false)")
    cmd = find_tesseract(settings.tesseract_cmd)
    if not cmd:
        return Check("tesseract", "fail", "tesseract not found — brew install tesseract tesseract-lang")
    missing = missing_languages(cmd, settings.ocr_language)
    data = {"path": cmd, "version": tesseract_version(cmd), "missing_languages": missing,
            "languages": settings.ocr_language.split("+")}
    if missing:
        return Check("tesseract", "fail", f"Missing language data: {', '.join(missing)} "
                     "(brew install tesseract-lang)", data)
    return Check("tesseract", "ok", f"{data['version']} · {settings.ocr_language}", data)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def check_telegram(settings: Settings) -> Check:
    if not settings.telegram_configured:
        return Check("telegram", "fail", "TUC_TELEGRAM_API_ID / TUC_TELEGRAM_API_HASH not set")
    session = settings.telegram_session_file
    if not session.exists():
        return Check("telegram", "warn", "No Telegram session — run: python -m app.cli telegram-login")
    mode = _mode(session)
    if mode & 0o077:
        return Check("telegram", "warn", f"Session file permissions are {oct(mode)}, expected 0o600",
                     {"path": str(session)})
    return Check("telegram", "ok", "Session present", {"path": str(session)})


def check_openai(settings: Settings) -> Check:
    if settings.ai_provider == AIProvider.NONE:
        return Check("openai", "warn", "AI provider disabled — rule-based classification only")
    if not settings.openai_configured:
        return Check("openai", "fail", "TUC_AI_PROVIDER=openai but TUC_OPENAI_API_KEY is empty")
    return Check("openai", "ok", f"Configured · {settings.openai_model}",
                 {"model": settings.openai_model})


def check_storage(settings: Settings) -> Check:
    root = settings.storage_root
    root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(root)
    data = {"path": str(root), "total": usage.total, "used": usage.used, "free": usage.free}
    free_pct = usage.free / usage.total if usage.total else 0
    level: Level = "ok" if free_pct > 0.1 else "warn" if free_pct > 0.03 else "fail"
    return Check("storage", level, f"{usage.free / 1e9:.1f} GB free", data)


def check_secret_permissions(settings: Settings) -> Check:
    problems: list[str] = []
    env_file = PROJECT_ROOT / ".env"
    for path in (env_file, settings.telegram_session_file):
        if path.exists() and _mode(path) & 0o077:
            problems.append(f"{path.name} is {oct(_mode(path))} (chmod 600)")
    if problems:
        return Check("permissions", "warn", "; ".join(problems))
    return Check("permissions", "ok", "Sensitive files are private (600)")


def check_lock(settings: Settings) -> Check:
    st = lock_status(settings.lock_path)
    if st.locked:
        return Check("lock", "warn", "A job is running", {"holder": st.holder})
    return Check("lock", "ok", "Idle", {"holder": None})


def check_launchd(settings: Settings) -> Check:
    from app.runtime.launchd import LaunchdManager

    try:
        agents = LaunchdManager(settings).status()
    except Exception as exc:
        return Check("launchd", "warn", f"launchctl unavailable: {exc}")
    data = {"agents": [asdict(a) for a in agents]}
    loaded = [a for a in agents if a.loaded]
    if not loaded:
        return Check("launchd", "warn", "No LaunchAgents loaded (launchd install)", data)
    failing = [a.label for a in loaded if a.last_exit_code not in (None, 0, 75)]
    if failing:
        return Check("launchd", "warn", f"Last run failed: {', '.join(failing)}", data)
    return Check("launchd", "ok", f"{len(loaded)}/{len(agents)} agents loaded", data)


def run_health_checks(settings: Settings, *, include_launchd: bool = True) -> list[Check]:
    checks = [
        check_mysql(settings),
        check_tesseract(settings),
        check_telegram(settings),
        check_openai(settings),
        check_storage(settings),
        check_secret_permissions(settings),
        check_lock(settings),
    ]
    if include_launchd:
        checks.append(check_launchd(settings))
    return checks
