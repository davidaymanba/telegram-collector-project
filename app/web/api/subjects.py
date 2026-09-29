from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.database.enums import FileStatus
from app.database.models import Classification, CollectedFile, Subject
from app.database.repositories import SubjectRepository
from app.web.deps import DB, User
from app.web.schemas import SubjectIn, SubjectOut, SubjectPatch

router = APIRouter(prefix="/subjects", tags=["subjects"])


def _out(s: Subject, counts: dict[str, dict[str, int]]) -> SubjectOut:
    out = SubjectOut.model_validate(s)
    out.counts = counts.get(s.code, {})
    out.total = sum(out.counts.values())
    return out


def _get(repo: SubjectRepository, subject_id: int) -> Subject:
    s = repo.get(subject_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found")
    return s


@router.get("", response_model=list[SubjectOut])
def list_subjects(db: DB, _: User) -> list[SubjectOut]:
    repo = SubjectRepository(db)
    counts = repo.counts_by_type()
    return [_out(s, counts) for s in repo.list_all()]


@router.post("", response_model=SubjectOut, status_code=201)
def create_subject(body: SubjectIn, db: DB, _: User) -> SubjectOut:
    s = Subject(code=body.code, name_ar=body.name_ar, name_en=body.name_en, keywords=body.keywords)
    try:
        SubjectRepository(db).add(s)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, f"Subject {body.code} already exists") from exc
    return _out(s, {})


@router.patch("/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: int, body: SubjectPatch, db: DB, _: User) -> SubjectOut:
    repo = SubjectRepository(db)
    s = _get(repo, subject_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(s, key, value)
    db.flush()
    return _out(s, repo.counts_by_type())


@router.delete("/{subject_id}", status_code=204)
def delete_subject(subject_id: int, db: DB, _: User, force: bool = False) -> None:
    repo = SubjectRepository(db)
    s = _get(repo, subject_id)
    used = db.scalar(select(func.count()).select_from(Classification)
                     .where(Classification.subject_code == s.code)) or 0
    if used and not force:
        raise HTTPException(409, f"{used} file(s) are classified under {s.code}; "
                                 "pass force=true to delete and mark them unclassified")
    if used:
        affected = select(Classification.file_id).where(Classification.subject_code == s.code)
        db.execute(update(CollectedFile).where(CollectedFile.id.in_(affected.scalar_subquery()))
                   .values(status=FileStatus.UNCLASSIFIED))
        db.execute(update(Classification).where(Classification.subject_code == s.code)
                   .values(subject_code=None, status="unclassified",
                           reason=f"Subject {s.code} was deleted"))
    repo.delete(s)
