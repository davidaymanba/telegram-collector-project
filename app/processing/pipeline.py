"""Process downloaded files: extract → normalise → store text → classify → file away."""

from __future__ import annotations

import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings
from app.database.enums import ClassificationStatus, FileStatus, ProcessingLogStatus
from app.database.models import CollectedFile
from app.database.repositories import (
    ClassificationRepository,
    FileRepository,
    ProcessingLogRepository,
    SubjectRepository,
)
from app.logging import get_logger
from app.processing.classifiers.base import (
    ClassificationInput,
    ClassificationOutcome,
    SubjectInfo,
)
from app.processing.classifiers.openai_classifier import ResponsesClient
from app.processing.classifiers.service import Classifier
from app.processing.extractors.base import extract_text
from app.processing.text import clean_text
from app.runtime.runs import RunContext
from app.storage.paths import StorageLayout, move_file, write_private_text

log = get_logger("tuc.process")


@dataclass(slots=True)
class FileOutcome:
    file_id: int
    status: FileStatus
    detail: str | None = None


def load_subjects(session: Session) -> list[SubjectInfo]:
    return [SubjectInfo(s.code, s.name_ar, s.name_en, list(s.keywords or []))
            for s in SubjectRepository(session).list_all()]


class Processor:
    def __init__(self, settings: Settings, session: Session, *,
                 openai_client: ResponsesClient | None = None) -> None:
        self.settings = settings
        self.session = session
        self.layout = StorageLayout(settings)
        self.layout.ensure()
        self.files = FileRepository(session)
        self.logs = ProcessingLogRepository(session)
        self.classifications = ClassificationRepository(session)
        self.classifier = Classifier(settings, openai_client)

    # ------------------------------------------------------------------ helpers
    def _log(self, f: CollectedFile, stage: str, status: ProcessingLogStatus,
             run: RunContext | None, message: str | None = None, error: str | None = None) -> None:
        self.logs.record(stage=stage, status=status, file_id=f.id,
                         run_id=run.run_id if run else None, message=message, error=error)

    def _input(self, f: CollectedFile, text: str, subjects: list[SubjectInfo]) -> ClassificationInput:
        msg = f.message
        return ClassificationInput(
            filename=f.original_filename,
            caption=(msg.caption or "") if msg else "",
            channel_name=msg.channel.name if msg and msg.channel else "",
            text=text,
            subjects=subjects,
        )

    def _file_away(self, f: CollectedFile, outcome: ClassificationOutcome) -> Path | None:
        if not f.storage_path:
            return None
        src = self.layout.check(Path(f.storage_path))
        if not src.exists():
            raise FileNotFoundError(f"Stored file is missing: {src}")
        if outcome.classified and outcome.subject_code and outcome.content_type:
            dest = self.layout.processed_path(outcome.subject_code, outcome.content_type, f.id,
                                              f.original_filename)
        else:
            dest = self.layout.unclassified_path(f.id, f.original_filename)
        if src.parent == dest.parent and src.name.startswith(f"{f.id}_"):
            return src  # already in place (e.g. reclassify with same result)
        return move_file(src, dest)

    def apply_outcome(self, f: CollectedFile, outcome: ClassificationOutcome,
                      run: RunContext | None) -> FileStatus:
        self.classifications.upsert(
            f.id, status=outcome.status, subject_code=outcome.subject_code,
            content_type=outcome.content_type, confidence=outcome.confidence,
            evidence=outcome.evidence, reason=outcome.reason,
            classifier_version=outcome.classifier_version,
        )
        self._log(f, "classify", ProcessingLogStatus.SUCCESS, run,
                  f"{outcome.status.value} by {outcome.classifier_version}"
                  + (f": {outcome.subject_code}/{outcome.content_type}" if outcome.classified
                     else f": {outcome.reason}"))
        new_path = self._file_away(f, outcome)
        if new_path is not None:
            f.storage_path = str(new_path)
            self._log(f, "move", ProcessingLogStatus.SUCCESS, run,
                      str(new_path.relative_to(self.layout.root)))
        f.status = (FileStatus.CLASSIFIED if outcome.status == ClassificationStatus.CLASSIFIED
                    else FileStatus.UNCLASSIFIED)
        f.error_message = None
        return f.status

    # ------------------------------------------------------------------ stages
    def process_file(self, f: CollectedFile, subjects: list[SubjectInfo],
                     run: RunContext | None = None) -> FileOutcome:
        f.status = FileStatus.PROCESSING
        self.session.commit()
        try:
            if not f.storage_path:
                raise FileNotFoundError("File has no storage path")
            path = self.layout.check(Path(f.storage_path))
            result = extract_text(path, f.extension, self.settings)
            text = clean_text(result.text)
            self._log(f, "extract", ProcessingLogStatus.SUCCESS, run,
                      f"{result.method}: {len(text)} chars"
                      + (f", {result.pages} pages" if result.pages else "")
                      + ("; " + "; ".join(result.warnings) if result.warnings else ""))
            text_path = self.layout.text_path(f.id)
            write_private_text(text_path, text)
            f.extracted_text_path = str(text_path)
            outcome = self.classifier.classify(self._input(f, text, subjects))
            status = self.apply_outcome(f, outcome, run)
            self.session.commit()
            return FileOutcome(f.id, status, outcome.reason)
        except Exception as exc:
            self.session.rollback()
            f = self.files.get(f.id) or f
            f.status = FileStatus.FAILED
            f.error_message = f"{type(exc).__name__}: {exc}"[:2000]
            self._log(f, "process", ProcessingLogStatus.FAILED, run, error=
                      traceback.format_exc(limit=4)[-2000:])
            self.session.commit()
            log.warning("file_failed", file_id=f.id, error=f.error_message)
            return FileOutcome(f.id, FileStatus.FAILED, f.error_message)

    def process_pending(self, *, limit: int | None = None, run: RunContext | None = None,
                        file_ids: Sequence[int] | None = None,
                        include_failed: bool = False) -> list[FileOutcome]:
        statuses = [FileStatus.DOWNLOADED, FileStatus.PROCESSING]
        if include_failed or file_ids:
            statuses.append(FileStatus.FAILED)
        if file_ids:
            statuses += [FileStatus.CLASSIFIED, FileStatus.UNCLASSIFIED]
        pending = list(self.files.list_by_status(statuses, limit=limit, file_ids=file_ids))
        subjects = load_subjects(self.session)
        outcomes: list[FileOutcome] = []
        total = len(pending)
        log.info("process_started", pending=total)
        for index, f in enumerate(pending, start=1):
            outcome = self.process_file(f, subjects, run)
            outcomes.append(outcome)
            if run:
                run.bump(outcome.status.value)
                run.progress(index, total, file_id=f.id, status=outcome.status.value)
            log.info("file_processed", file_id=f.id, name=f.original_filename,
                     status=outcome.status.value, detail=outcome.detail)
        return outcomes

    def reclassify(self, *, statuses: Sequence[FileStatus], limit: int | None = None,
                   run: RunContext | None = None) -> list[FileOutcome]:
        """Re-run classification on already extracted text (no OCR/extraction)."""
        files = list(self.files.list_by_status(statuses, limit=limit))
        subjects = load_subjects(self.session)
        outcomes: list[FileOutcome] = []
        for index, f in enumerate(files, start=1):
            if not f.extracted_text_path or not Path(f.extracted_text_path).exists():
                outcomes.append(self.process_file(f, subjects, run))
            else:
                try:
                    text = Path(f.extracted_text_path).read_text(encoding="utf-8")
                    outcome = self.classifier.classify(self._input(f, text, subjects))
                    status = self.apply_outcome(f, outcome, run)
                    self.session.commit()
                    outcomes.append(FileOutcome(f.id, status, outcome.reason))
                except Exception as exc:
                    self.session.rollback()
                    self._log(f, "reclassify", ProcessingLogStatus.FAILED, run, error=str(exc))
                    self.session.commit()
                    outcomes.append(FileOutcome(f.id, FileStatus.FAILED, str(exc)))
            if run:
                run.bump(outcomes[-1].status.value)
                run.progress(index, len(files), file_id=f.id)
        return outcomes

    def manual_classify(self, f: CollectedFile, subject_code: str, content_type: str) -> None:
        outcome = ClassificationOutcome(
            status=ClassificationStatus.CLASSIFIED, subject_code=subject_code,
            content_type=content_type, confidence=1.0, evidence=["Manually classified"],
            reason="Manual classification from dashboard", classifier_version="manual",
        )
        self.apply_outcome(f, outcome, None)
        self.session.commit()
