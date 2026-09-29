from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.runtime.lock import lock_status
from app.web.deps import SettingsDep, User
from app.web.jobs.manager import Job, JobConflictError, JobManager
from app.web.schemas import JobIn, JobOut, LockOut

router = APIRouter(prefix="/jobs", tags=["jobs"])
HEARTBEAT_SECONDS = 15


def _manager(request: Request) -> JobManager:
    return request.app.state.jobs  # type: ignore[no-any-return]


def _out(job: Job) -> JobOut:
    return JobOut(**job.summary())


@router.get("/lock", response_model=LockOut)
def lock(request: Request, _: User, settings: SettingsDep) -> LockOut:
    st = lock_status(settings.lock_path)
    active = _manager(request).active()
    return LockOut(locked=st.locked or active is not None, holder=st.holder,
                   active_job=_out(active) if active else None)


@router.get("", response_model=list[JobOut])
def list_jobs(request: Request, _: User) -> list[JobOut]:
    return [_out(j) for j in _manager(request).recent()]


@router.post("", response_model=JobOut, status_code=202)
def start_job(body: JobIn, request: Request, _: User, settings: SettingsDep) -> JobOut:
    args: list[str] = []
    if body.kind == "collect":
        if not settings.telegram_configured:
            raise HTTPException(422, "Telegram credentials are not configured")
        if body.channel:
            args += ["--channel", body.channel]
    if body.limit:
        args += ["--limit", str(body.limit)]
    try:
        job = _manager(request).start(body.kind, args)
    except JobConflictError as exc:
        raise HTTPException(409, {"message": "A job is already running",
                                  "holder": exc.holder}) from exc
    return _out(job)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, request: Request, _: User) -> JobOut:
    job = _manager(request).get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return _out(job)


def _sse(event: str, data: Any, event_id: int | None = None) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {event}\ndata: {payload}\n\n"


@router.get("/{job_id}/stream")
async def stream(job_id: str, request: Request, _: User) -> StreamingResponse:
    """Server-Sent Events: `log` for each line, `status` for progress, `end` when finished."""
    job = _manager(request).get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    try:
        start = int(request.headers.get("last-event-id") or 0)
    except ValueError:
        start = 0

    async def events() -> AsyncIterator[str]:
        seq = start
        idle = 0.0
        yield "retry: 2000\n\n"
        while True:
            if await request.is_disconnected():
                return
            batch = job.since(seq)
            for entry in batch:
                seq = entry["seq"]
                yield _sse("log", entry, seq)
            if batch:
                idle = 0.0
                yield _sse("status", job.summary())
            if job.done and not job.since(seq):
                yield _sse("end", job.summary())
                return
            await asyncio.to_thread(job.wait, seq, 1.0)
            idle += 1.0
            if idle >= HEARTBEAT_SECONDS:
                idle = 0.0
                yield ": keep-alive\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive",
    })
