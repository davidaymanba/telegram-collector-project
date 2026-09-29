from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def make_engine(url: str) -> Engine:
    if not url.startswith("mysql"):
        raise ValueError("TUC only supports MySQL (mysql+pymysql://...)")
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_session(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        with dbapi_conn.cursor() as cur:
            cur.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
            cur.execute("SET time_zone = '+00:00'")

    return engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return make_engine(get_settings().database_url.get_secret_value())


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def reset_engine() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
