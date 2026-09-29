from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.logging import get_logger
from app.web.auth.security import (
    CSRF_COOKIE,
    CSRF_HEADER,
    csrf_matches,
    new_csrf_token,
    verify_credentials,
)
from app.web.deps import SettingsDep, User
from app.web.schemas import LoginIn, MeOut

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("tuc.web.auth")


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_csrf_cookie(response: Response, token: str, secure: bool) -> None:
    # Readable by JS on purpose (double-submit); the authoritative copy lives in the session.
    response.set_cookie(CSRF_COOKIE, token, httponly=False, samesite="strict", secure=secure,
                        path="/")


@router.post("/login", response_model=MeOut)
def login(body: LoginIn, request: Request, response: Response, settings: SettingsDep) -> MeOut:
    throttle = request.app.state.login_throttle
    key = _client_key(request)
    if wait := throttle.retry_after(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many attempts. Try again in {wait}s",
                            headers={"Retry-After": str(wait)})
    if settings.dashboard_password is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "DASHBOARD_PASSWORD is not configured on the server")
    if not verify_credentials(settings, body.username, body.password):
        throttle.failure(key)
        log.warning("login_failed", client=key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    throttle.reset(key)
    request.session.clear()
    token = new_csrf_token()
    request.session.update({"user": settings.dashboard_username, "csrf": token})
    _set_csrf_cookie(response, token, settings.is_production)
    log.info("login_ok", client=key)
    return MeOut(username=settings.dashboard_username, csrf_token=token)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> Response:
    if request.session.get("user") and not csrf_matches(
        request.session.get("csrf"), request.headers.get(CSRF_HEADER)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")
    request.session.clear()
    response.status_code = 204
    response.delete_cookie(CSRF_COOKIE, path="/")
    return response


@router.get("/me", response_model=MeOut)
def me(user: User, request: Request, response: Response, settings: SettingsDep) -> MeOut:
    token = str(request.session.get("csrf") or "")
    if not token:
        token = new_csrf_token()
        request.session["csrf"] = token
    _set_csrf_cookie(response, token, settings.is_production)
    return MeOut(username=user, csrf_token=token)
