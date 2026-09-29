"""FastAPI application: JSON API under /api/v1, the built SPA everywhere else."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import PROJECT_ROOT, Settings, get_settings
from app.database.session import get_engine
from app.logging import configure_logging, get_logger
from app.web.api import auth, channels, files, jobs, messages, overview, runs, subjects
from app.web.api import settings as settings_api
from app.web.auth.security import SESSION_COOKIE, LoginThrottle
from app.web.deps import current_user
from app.web.jobs.manager import JobManager

log = get_logger("tuc.web")
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
       "font-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
       "base-uri 'self'; form-action 'self'")


class SecurityHeaders:
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")

        async def _send(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                extra = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"same-origin",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
                }
                if not path.startswith("/api/docs"):
                    extra[b"content-security-policy"] = CSP.encode()
                if self.hsts:
                    extra[b"strict-transport-security"] = b"max-age=31536000"
                if path.startswith("/api/"):
                    extra[b"cache-control"] = b"no-store"
                present = {k.lower() for k, _ in headers}
                headers.extend((k, v) for k, v in extra.items() if k not in present)
            await send(message)

        await self.app(scope, receive, _send)


def _session_secret(settings: Settings) -> str:
    if settings.session_secret is not None and settings.session_secret.get_secret_value():
        return settings.session_secret.get_secret_value()
    if settings.is_production:
        raise RuntimeError("TUC_SESSION_SECRET must be set in production")
    log.warning("session_secret_missing",
                hint="Set TUC_SESSION_SECRET; sessions reset on every restart until you do")
    return secrets.token_urlsafe(48)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.effective_log_format)

    app = FastAPI(title="TUC API", version="1.0.0", docs_url=None, redoc_url=None,
                  openapi_url=None)
    app.state.settings = settings
    app.state.jobs = JobManager(settings)
    app.state.login_throttle = LoginThrottle(settings.login_max_attempts,
                                             settings.login_window_seconds)

    app.add_middleware(
        SessionMiddleware,
        secret_key=_session_secret(settings),
        session_cookie=SESSION_COOKIE,
        max_age=settings.session_max_age_seconds,
        same_site="strict",
        https_only=settings.is_production,
    )
    app.add_middleware(SecurityHeaders, hsts=settings.is_production)

    api = APIRouter(prefix="/api/v1")
    api.include_router(auth.router)
    for module in (overview, channels, subjects, files, messages, runs, jobs, settings_api):
        api.include_router(module.router)
    app.include_router(api)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> JSONResponse:
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return JSONResponse({"status": "ok", "db": "ok"})
        except Exception:
            return JSONResponse({"status": "degraded", "db": "unreachable"}, status_code=503)

    # OpenAPI docs are only served to logged-in users.
    @app.get("/api/openapi.json", include_in_schema=False, dependencies=[Depends(current_user)])
    def openapi_json() -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.get("/api/docs", include_in_schema=False, dependencies=[Depends(current_user)])
    def docs() -> HTMLResponse:
        return get_swagger_ui_html(openapi_url="/api/openapi.json", title="TUC API")

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                   include_in_schema=False)
    def api_not_found(rest: str) -> JSONResponse:
        return JSONResponse({"detail": "Not found"}, status_code=404)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    index = FRONTEND_DIST / "index.html"
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str, request: Request) -> Response:
        if index.exists():
            candidate = (FRONTEND_DIST / path).resolve()
            if (path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents):
                return FileResponse(candidate)
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return HTMLResponse(
            "<h1>TUC API is running</h1><p>The dashboard is not built yet. Run "
            "<code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>.</p>",
            status_code=200,
        )
