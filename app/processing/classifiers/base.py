from __future__ import annotations

from dataclasses import dataclass, field

from app.database.enums import ClassificationStatus


@dataclass(slots=True)
class SubjectInfo:
    code: str
    name_ar: str
    name_en: str
    keywords: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ClassificationInput:
    filename: str
    caption: str
    channel_name: str
    text: str
    subjects: list[SubjectInfo]


@dataclass(slots=True)
class ClassificationOutcome:
    status: ClassificationStatus
    subject_code: str | None
    content_type: str | None
    confidence: float | None
    evidence: list[str]
    reason: str | None
    classifier_version: str

    @property
    def classified(self) -> bool:
        return self.status == ClassificationStatus.CLASSIFIED


def unclassified(reason: str, version: str, *, subject_code: str | None = None,
                 content_type: str | None = None, confidence: float | None = None,
                 evidence: list[str] | None = None) -> ClassificationOutcome:
    return ClassificationOutcome(
        status=ClassificationStatus.UNCLASSIFIED, subject_code=subject_code,
        content_type=content_type, confidence=confidence, evidence=evidence or [],
        reason=reason, classifier_version=version,
    )
