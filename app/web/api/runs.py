from __future__ import annotations

import json
from collections import deque
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app.database.enums import RunKind
from app.database.repositories import ProcessingLogRepository, RunRepository
from app.runtime.runs import run_log_path
from app.web.deps import DB, SettingsDep, User
from app.web.jobs.manager import parse_line
from app.web.schemas import LogOut, PageOut, RunDetailOut, RunOut

router = APIRouter(prefix="/runs", tags=["runs"])
MAX_LOG_LINES = 2000


@router.get("", response_model=PageOut[RunOut])
def list_runs(
    db: DB, _: User, kind: RunKind | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> PageOut[RunOut]:
    result = RunRepository(db).search(kind=kind, page=page, page_size=page_size)
    return PageOut[RunOut](items=[RunOut.model_validate(r) for r in result.items],
                           total=result.total, page=page, page_size=page_size,
                           pages=result.pages)


@router.get("/{run_id}", response_model=RunDetailOut)
def run_detail(run_id: int, db: DB, _: User, settings: SettingsDep) -> RunDetailOut:
    run = RunRepository(db).get(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    lines: list[dict[str, Any]] = []
    path = run_log_path(settings, run_id)
    if path.exists():
        with path.open(encoding="utf-8", errors="replace") as fh:
            tail: deque[str] = deque(fh, maxlen=MAX_LOG_LINES)
        for i, raw in enumerate(tail, start=1):
            entry = parse_line(raw)
            entry["seq"] = i
            lines.append(json.loads(json.dumps(entry, default=str)))
    base = RunOut.model_validate(run).model_dump()
    return RunDetailOut(
        **base,
        logs=[LogOut.model_validate(x) for x in ProcessingLogRepository(db).for_run(run_id)],
        log_lines=lines,
    )
