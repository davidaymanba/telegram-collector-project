from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_sessionmaker
from app.web.auth.security import CSRF_HEADER, csrf_matches

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def current_user(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if request.method not in SAFE_METHODS and not csrf_matches(
        request.session.get("csrf"), request.headers.get(CSRF_HEADER)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")
    return str(user)


DB = Annotated[Session, Depends(get_db)]
User = Annotated[str, Depends(current_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
