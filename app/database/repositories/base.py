from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from app.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


@dataclass(slots=True)
class Page(Generic[ModelT]):
    items: list[ModelT]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.page_size))


class Repository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, id_: int) -> ModelT | None:
        return self.session.get(self.model, id_)

    def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        self.session.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.session.delete(obj)
        self.session.flush()
