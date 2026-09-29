from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.database.enums import CONTENT_TYPES, FileStatus
from app.database.models import CollectedFile
from app.database.repositories import FileRepository, RunRepository, SubjectRepository
from app.reports.reporter import build_report
from app.runtime.health import run_health_checks
from app.runtime.lock import lock_status
from app.web.deps import DB, SettingsDep, User
from app.web.schemas import FileOut, RunOut

router = APIRouter(tags=["overview"])

KPI_KEYS = ("total", "classified", "unclassified", "duplicate", "failed")


def _daily(db: DB, since: datetime) -> dict[date, dict[str, int]]:
    day = func.date(CollectedFile.created_at)
    rows = db.execute(
        select(day, CollectedFile.status, func.count())
        .where(CollectedFile.created_at >= since)
        .group_by(day, CollectedFile.status)
    ).all()
    out: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for d, st, n in rows:
        d = d if isinstance(d, date) else date.fromisoformat(str(d))
        key = st.value if isinstance(st, FileStatus) else str(st)
        out[d][key] += int(n)
        out[d]["total"] += int(n)
    return out


def _pct(current: int, previous: int) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return round((current - previous) / previous * 100, 1)


@router.get("/overview")
def overview(db: DB, _: User) -> dict[str, Any]:
    today = datetime.now(UTC).date()
    since = datetime.combine(today - timedelta(days=29), datetime.min.time(), UTC)
    daily = _daily(db, since)
    days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    series: list[dict[str, Any]] = [{"date": d.isoformat(), **{k: daily.get(d, {}).get(k, 0) for k in
               ("total", "classified", "unclassified", "duplicate", "failed", "unsupported")}}
              for d in days]

    counts = FileRepository(db).status_counts()
    totals = {"total": sum(counts.values()), **{k: counts.get(k, 0) for k in KPI_KEYS[1:]}}
    kpis = []
    for key in KPI_KEYS:
        spark = [row[key] for row in series[-14:]]
        last7 = sum(row[key] for row in series[-7:])
        prev7 = sum(row[key] for row in series[-14:-7])
        kpis.append({"key": key, "value": totals[key], "sparkline": spark, "last_7d": last7,
                     "change_pct": _pct(last7, prev7)})

    report = build_report(db)
    subjects = {s.code: s for s in SubjectRepository(db).list_all()}
    by_subject = [{"code": code, "name_ar": subjects[code].name_ar,
                   "name_en": subjects[code].name_en, "count": n}
                  for code, n in sorted(report.by_subject.items(), key=lambda kv: -kv[1])]
    last_run = RunRepository(db).latest(1)
    return {
        "kpis": kpis,
        "daily": series,
        "by_content_type": [{"content_type": t, "count": report.by_content_type.get(t, 0)}
                            for t in CONTENT_TYPES],
        "by_subject": by_subject,
        "empty_subjects": [{"code": c, "name_ar": subjects[c].name_ar,
                            "name_en": subjects[c].name_en} for c in report.empty_subjects],
        "recent_files": [FileOut.model_validate(f).model_dump() for f in
                         FileRepository(db).recent(10)],
        "last_run": RunOut.model_validate(last_run[0]).model_dump() if last_run else None,
        "pending": report.pending,
    }


@router.get("/report")
def report(db: DB, _: User) -> dict[str, Any]:
    return build_report(db).as_dict()


@router.get("/system/health")
def system_health(_: User, settings: SettingsDep) -> dict[str, Any]:
    checks = run_health_checks(settings)
    return {"checks": [c.as_dict() for c in checks],
            "checked_at": datetime.now(UTC).isoformat()}


@router.get("/system/status")
def system_status(db: DB, _: User, settings: SettingsDep) -> dict[str, Any]:
    """Cheap status for the sidebar indicator (polled)."""
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    lock = lock_status(settings.lock_path)
    return {
        "db": db_ok,
        "telegram": settings.telegram_configured and settings.telegram_session_file.exists(),
        "telegram_configured": settings.telegram_configured,
        "lock": {"locked": lock.locked, "holder": lock.holder},
        "ai_provider": settings.ai_provider.value,
    }
