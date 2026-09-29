from __future__ import annotations

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import TABLE_ARGS, Base, TimestampMixin


class Subject(TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = TABLE_ARGS

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    def __repr__(self) -> str:
        return f"<Subject {self.code}>"
