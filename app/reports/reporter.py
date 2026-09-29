from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.database.enums import CONTENT_TYPES
from app.database.repositories import ClassificationRepository, FileRepository, SubjectRepository


@dataclass(slots=True)
class Report:
    total: int
    new: int
    duplicates: int
    classified: int
    unclassified: int
    failed: int
    unsupported: int
    pending: int
    by_subject: dict[str, int] = field(default_factory=dict)
    by_content_type: dict[str, int] = field(default_factory=dict)
    empty_subjects: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_report(session: Session) -> Report:
    counts = FileRepository(session).status_counts()
    cls = ClassificationRepository(session)
    by_subject = cls.counts_by("subject_code")
    by_type = dict.fromkeys(CONTENT_TYPES, 0) | cls.counts_by("content_type")
    subjects = SubjectRepository(session).codes()
    return Report(
        total=sum(counts.values()),
        new=counts.get("downloaded", 0) + counts.get("classified", 0)
        + counts.get("unclassified", 0) + counts.get("processing", 0),
        duplicates=counts.get("duplicate", 0),
        classified=counts.get("classified", 0),
        unclassified=counts.get("unclassified", 0),
        failed=counts.get("failed", 0),
        unsupported=counts.get("unsupported", 0),
        pending=counts.get("downloaded", 0) + counts.get("discovered", 0)
        + counts.get("processing", 0),
        by_subject={code: by_subject.get(code, 0) for code in subjects},
        by_content_type=by_type,
        empty_subjects=[code for code in subjects if not by_subject.get(code)],
    )


def format_report(report: Report) -> str:
    lines = [
        "TUC report",
        "==========",
        f"Total files     {report.total:>8}",
        f"New (unique)    {report.new:>8}",
        f"Duplicates      {report.duplicates:>8}",
        f"Classified      {report.classified:>8}",
        f"Unclassified    {report.unclassified:>8}",
        f"Failed          {report.failed:>8}",
        f"Unsupported     {report.unsupported:>8}",
        f"Pending         {report.pending:>8}",
        "",
        "By subject",
        "----------",
        *[f"  {code:<14}{n:>8}" for code, n in report.by_subject.items()],
        "",
        "By content type",
        "---------------",
        *[f"  {ctype:<14}{n:>8}" for ctype, n in report.by_content_type.items()],
    ]
    if report.empty_subjects:
        lines += ["", "Subjects with no content: " + ", ".join(report.empty_subjects)]
    return "\n".join(lines)
