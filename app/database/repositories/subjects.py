from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import func, select

from app.database.enums import ClassificationStatus
from app.database.models import Classification, Subject
from app.database.repositories.base import Repository


class SubjectRepository(Repository[Subject]):
    model = Subject

    def list_all(self) -> Sequence[Subject]:
        return self.session.scalars(select(Subject).order_by(Subject.code)).all()

    def get_by_code(self, code: str) -> Subject | None:
        return self.session.scalar(select(Subject).where(Subject.code == code.upper()))

    def codes(self) -> list[str]:
        return list(self.session.scalars(select(Subject.code).order_by(Subject.code)))

    def counts_by_type(self) -> dict[str, dict[str, int]]:
        rows = self.session.execute(
            select(Classification.subject_code, Classification.content_type, func.count())
            .where(Classification.status == ClassificationStatus.CLASSIFIED)
            .group_by(Classification.subject_code, Classification.content_type)
        ).all()
        out: dict[str, dict[str, int]] = defaultdict(dict)
        for code, ctype, n in rows:
            if code and ctype:
                out[code][ctype] = int(n)
        return dict(out)
