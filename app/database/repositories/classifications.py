from __future__ import annotations

from sqlalchemy import func, select

from app.database.enums import ClassificationStatus
from app.database.models import Classification
from app.database.repositories.base import Repository


class ClassificationRepository(Repository[Classification]):
    model = Classification

    def get_for_file(self, file_id: int) -> Classification | None:
        return self.session.scalar(select(Classification).where(Classification.file_id == file_id))

    def upsert(
        self,
        file_id: int,
        *,
        status: ClassificationStatus,
        subject_code: str | None,
        content_type: str | None,
        confidence: float | None,
        evidence: list[str],
        reason: str | None,
        classifier_version: str,
    ) -> Classification:
        obj = self.get_for_file(file_id)
        if obj is None:
            obj = Classification(file_id=file_id)
            self.session.add(obj)
        obj.status = status
        obj.subject_code = subject_code
        obj.content_type = content_type
        obj.confidence = confidence
        obj.evidence = list(evidence)
        obj.reason = reason
        obj.classifier_version = classifier_version
        self.session.flush()
        return obj

    def counts_by(self, column: str) -> dict[str, int]:
        col = getattr(Classification, column)
        rows = self.session.execute(
            select(col, func.count())
            .where(Classification.status == ClassificationStatus.CLASSIFIED, col.is_not(None))
            .group_by(col)
        ).all()
        return {str(k): int(n) for k, n in rows}
