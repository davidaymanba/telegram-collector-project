from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.database.enums import CONTENT_TYPES, FileStatus
from app.database.models import CollectedFile
from app.database.repositories import (
    FileFilters,
    FileRepository,
    ProcessingLogRepository,
    SubjectRepository,
)
from app.processing.pipeline import Processor
from app.runtime.lock import JobLock, LockBusyError
from app.storage.paths import StorageLayout, UnsafePathError
from app.web.deps import DB, SettingsDep, User
from app.web.schemas import (
    FacetsOut,
    FileDetailOut,
    FileOut,
    LogOut,
    ManualClassifyIn,
    PageOut,
)

router = APIRouter(prefix="/files", tags=["files"])
PREVIEW_CHARS = 20_000


def _get(db: DB, file_id: int) -> CollectedFile:
    f = FileRepository(db).get_detail(file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return f


def _safe_disk_path(layout: StorageLayout, raw: str | None) -> Path | None:
    if not raw:
        return None
    try:
        return layout.check(Path(raw))
    except UnsafePathError:
        return None


@router.get("", response_model=PageOut[FileOut])
def list_files(
    db: DB,
    _: User,
    q: str | None = None,
    status_: Annotated[list[FileStatus] | None, Query(alias="status")] = None,
    subject: str | None = None,
    content_type: str | None = None,
    extension: str | None = None,
    channel_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: Literal["created_at", "original_filename", "size_bytes", "status",
                  "message_date"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> PageOut[FileOut]:
    filters = FileFilters(q=q.strip() if q else None, status=status_, subject_code=subject,
                          content_type=content_type, extension=extension,
                          channel_id=channel_id, date_from=date_from, date_to=date_to)
    result = FileRepository(db).search(filters, sort=sort, order=order, page=page,
                                       page_size=page_size)
    return PageOut[FileOut](items=[FileOut.model_validate(f) for f in result.items],
                            total=result.total, page=page, page_size=page_size,
                            pages=result.pages)


@router.get("/facets", response_model=FacetsOut)
def facets(db: DB, _: User) -> FacetsOut:
    repo = FileRepository(db)
    return FacetsOut(extensions=repo.extensions(), statuses=[s.value for s in FileStatus],
                     content_types=list(CONTENT_TYPES), subjects=SubjectRepository(db).codes(),
                     status_counts=repo.status_counts())


@router.get("/{file_id}", response_model=FileDetailOut)
def file_detail(file_id: int, db: DB, _: User, settings: SettingsDep) -> FileDetailOut:
    f = _get(db, file_id)
    layout = StorageLayout(settings)
    disk = _safe_disk_path(layout, f.storage_path)
    text_path = _safe_disk_path(layout, f.extracted_text_path)
    preview, length = None, 0
    if text_path and text_path.exists():
        content = text_path.read_text(encoding="utf-8", errors="replace")
        length = len(content)
        preview = content[:PREVIEW_CHARS]
    ch = f.message.channel
    link = (f"https://t.me/{ch.username}/{f.message.telegram_message_id}"
            if ch.username and not ch.username.startswith("demo_") else None)
    base = FileOut.model_validate(f).model_dump()
    return FileDetailOut(
        **base,
        storage_path=str(disk) if disk else None,
        relative_path=str(disk.relative_to(layout.root.resolve())) if disk else None,
        exists_on_disk=bool(disk and disk.exists()),
        text_preview=preview,
        text_length=length,
        telegram_link=link,
        message_metadata=f.message.telegram_metadata or {},
        logs=[LogOut.model_validate(x) for x in ProcessingLogRepository(db).for_file(f.id)],
    )


@router.get("/{file_id}/download")
def download(file_id: int, db: DB, _: User, settings: SettingsDep) -> FileResponse:
    f = _get(db, file_id)
    disk = _safe_disk_path(StorageLayout(settings), f.storage_path)
    if disk is None or not disk.exists():
        raise HTTPException(404, "File is not stored on disk")
    return FileResponse(disk, filename=f.original_filename,
                        media_type=f.mime_type or "application/octet-stream")


@router.post("/{file_id}/reveal", status_code=204)
def reveal_in_finder(file_id: int, db: DB, _: User, settings: SettingsDep) -> None:
    """Open Finder with the file selected (macOS). The server only ever runs on 127.0.0.1."""
    f = _get(db, file_id)
    disk = _safe_disk_path(StorageLayout(settings), f.storage_path)
    if disk is None or not disk.exists():
        raise HTTPException(404, "File is not stored on disk")
    if sys.platform != "darwin":
        raise HTTPException(501, "Reveal in Finder is only available on macOS")
    subprocess.run(["open", "-R", str(disk)], check=False, timeout=10)


@router.post("/{file_id}/reprocess", response_model=FileOut)
def reprocess(file_id: int, db: DB, _: User, settings: SettingsDep) -> FileOut:
    f = _get(db, file_id)
    if f.status in (FileStatus.DUPLICATE, FileStatus.UNSUPPORTED) or not f.storage_path:
        raise HTTPException(409, f"Cannot reprocess a file with status '{f.status.value}'")
    try:
        with JobLock(settings.lock_path, kind="process", trigger="web"):
            Processor(settings, db).process_pending(file_ids=[file_id])
    except LockBusyError as exc:
        raise HTTPException(423, "Another job is running — try again when it finishes") from exc
    db.expire_all()
    return FileOut.model_validate(_get(db, file_id))


@router.post("/{file_id}/classify", response_model=FileOut)
def manual_classify(file_id: int, body: ManualClassifyIn, db: DB, _: User,
                    settings: SettingsDep) -> FileOut:
    f = _get(db, file_id)
    if SubjectRepository(db).get_by_code(body.subject_code) is None:
        raise HTTPException(422, f"Unknown subject {body.subject_code}")
    if f.status in (FileStatus.DUPLICATE, FileStatus.UNSUPPORTED):
        raise HTTPException(409, f"Cannot classify a file with status '{f.status.value}'")
    try:
        with JobLock(settings.lock_path, kind="classify", trigger="web"):
            Processor(settings, db).manual_classify(f, body.subject_code.upper(),
                                                    body.content_type)
    except LockBusyError as exc:
        raise HTTPException(423, "Another job is running — try again when it finishes") from exc
    db.expire_all()
    return FileOut.model_validate(_get(db, file_id))
