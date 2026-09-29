from __future__ import annotations

import io
import json
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.enums import FileStatus
from app.database.models import Channel, Subject
from app.runtime.lock import JobLock
from app.web.app import create_app
from app.web.auth.security import CSRF_HEADER, hash_password
from tests.conftest import TEST_PASSWORD, make_file
from tests.factories import make_pdf


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def auth(client: TestClient) -> TestClient:
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert r.status_code == 200, r.text
    client.headers[CSRF_HEADER] = r.json()["csrf_token"]
    return client


# ------------------------------------------------------------------ auth & security
def test_healthz_is_public(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["db"] == "ok"


@pytest.mark.parametrize("path", ["/api/v1/overview", "/api/v1/files", "/api/v1/channels",
                                  "/api/v1/settings", "/api/docs", "/api/openapi.json",
                                  "/api/v1/auth/me"])
def test_endpoints_require_login(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401


def test_default_docs_routes_disabled(client: TestClient) -> None:
    assert client.get("/docs").status_code in (200, 404)
    assert "swagger" not in client.get("/docs").text.lower()
    assert client.get("/openapi.json").headers["content-type"].startswith("text/html")


def test_login_flow_and_cookie_flags(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert r.status_code == 200
    cookies = r.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith("tuc_session="))
    assert "httponly" in session.lower() and "samesite=strict" in session.lower()
    assert "secure" not in session.lower()  # development
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["username"] == "admin"
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").json()["info"]["title"] == "TUC API"


def test_wrong_password_and_rate_limit(client: TestClient) -> None:
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
        assert r.status_code == 401
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_login_with_argon2_hash(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import SecretStr

    settings.dashboard_password = SecretStr(hash_password("s3cret"))
    with TestClient(create_app(settings)) as c:
        ok = c.post("/api/v1/auth/login", json={"username": "admin", "password": "s3cret"})
        assert ok.status_code == 200
        bad = c.post("/api/v1/auth/login", json={"username": "root", "password": "s3cret"})
        assert bad.status_code == 401


def test_csrf_required_for_mutations(auth: TestClient) -> None:
    token = auth.headers.pop(CSRF_HEADER)
    r = auth.post("/api/v1/channels", json={"name": "x", "username": "chan_x"})
    assert r.status_code == 403
    auth.headers[CSRF_HEADER] = "forged"
    assert auth.post("/api/v1/channels", json={"name": "x", "username": "chan_x"}
                     ).status_code == 403
    auth.headers[CSRF_HEADER] = token
    assert auth.post("/api/v1/channels", json={"name": "x", "username": "chan_x"}
                     ).status_code == 201


def test_logout(auth: TestClient) -> None:
    assert auth.post("/api/v1/auth/logout").status_code == 204
    assert auth.get("/api/v1/auth/me").status_code == 401


def test_security_headers(auth: TestClient) -> None:
    r = auth.get("/api/v1/channels")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_unknown_api_route_is_json_404(auth: TestClient) -> None:
    r = auth.get("/api/v1/nope")
    assert r.status_code == 404 and r.json() == {"detail": "Not found"}


# ------------------------------------------------------------------ CRUD
def test_channels_crud(auth: TestClient) -> None:
    r = auth.post("/api/v1/channels", json={"name": "دفعة", "username": "@cs_batch_26"})
    assert r.status_code == 201
    ch = r.json()
    assert ch["username"] == "cs_batch_26" and ch["status"] == "idle" and ch["file_count"] == 0
    assert auth.post("/api/v1/channels", json={"name": "dup", "username": "cs_batch_26"}
                     ).status_code == 409
    assert auth.post("/api/v1/channels", json={"name": "noid"}).status_code == 422
    assert auth.post("/api/v1/channels", json={"name": "bad", "username": "a b"}
                     ).status_code == 422
    r = auth.patch(f"/api/v1/channels/{ch['id']}", json={"enabled": False})
    assert r.json()["enabled"] is False and r.json()["status"] == "disabled"
    assert len(auth.get("/api/v1/channels").json()) == 1
    assert auth.delete(f"/api/v1/channels/{ch['id']}").status_code == 204
    assert auth.delete(f"/api/v1/channels/{ch['id']}").status_code == 404


def test_subjects_crud(auth: TestClient, db: Session, channel: Channel) -> None:
    r = auth.post("/api/v1/subjects", json={"code": "net301", "name_ar": "شبكات",
                                           "name_en": "Networks",
                                           "keywords": ["TCP", "tcp", " osi "]})
    assert r.status_code == 201
    s = r.json()
    assert s["code"] == "NET301" and s["keywords"] == ["TCP", "osi"]
    assert auth.post("/api/v1/subjects", json={"code": "NET301", "name_ar": "x",
                                               "name_en": "y"}).status_code == 409
    assert auth.post("/api/v1/subjects", json={"code": "!", "name_ar": "x",
                                               "name_en": "y"}).status_code == 422
    r = auth.patch(f"/api/v1/subjects/{s['id']}", json={"keywords": ["udp"]})
    assert r.json()["keywords"] == ["udp"]

    # A subject in use needs force=true, and its files become unclassified.
    f = make_file(db, channel, None, name="x.pdf", msg_id=1, status=FileStatus.CLASSIFIED)
    from app.database.enums import ClassificationStatus
    from app.database.repositories import ClassificationRepository

    ClassificationRepository(db).upsert(f.id, status=ClassificationStatus.CLASSIFIED,
                                        subject_code="NET301", content_type="lecture",
                                        confidence=1, evidence=["m"], reason=None,
                                        classifier_version="manual")
    db.commit()
    subjects = auth.get("/api/v1/subjects").json()
    assert subjects[0]["counts"] == {"lecture": 1} and subjects[0]["total"] == 1
    assert auth.delete(f"/api/v1/subjects/{s['id']}").status_code == 409
    assert auth.delete(f"/api/v1/subjects/{s['id']}?force=true").status_code == 204
    db.expire_all()
    db.refresh(f)
    assert f.status == FileStatus.UNCLASSIFIED


def test_files_list_detail_and_actions(auth: TestClient, settings: Settings, db: Session,
                                       channel: Channel, subjects: list[Subject]) -> None:
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)
    p = make_pdf(settings.incoming_dir / "a.pdf", ["Database lecture about SQL and ERD"])
    f = make_file(db, channel, p, name="DB101 Lecture 1.pdf", msg_id=7, caption="محاضرة")
    make_file(db, channel, None, name="old.doc", msg_id=8, status=FileStatus.UNSUPPORTED)

    page = auth.get("/api/v1/files", params={"page_size": 1}).json()
    assert page["total"] == 2 and page["pages"] == 2 and len(page["items"]) == 1
    assert auth.get("/api/v1/files", params={"status": "unsupported"}).json()["total"] == 1
    assert auth.get("/api/v1/files", params={"q": "Lecture"}).json()["total"] == 1
    assert auth.get("/api/v1/files", params={"extension": "doc"}).json()["total"] == 1
    assert auth.get("/api/v1/files", params={"sort": "bogus"}).status_code == 422
    facets = auth.get("/api/v1/files/facets").json()
    assert set(facets["extensions"]) == {"pdf", "doc"} and "DB101" in facets["subjects"]

    r = auth.post(f"/api/v1/files/{f.id}/reprocess")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "classified"
    assert r.json()["classification"]["subject_code"] == "DB101"

    detail = auth.get(f"/api/v1/files/{f.id}").json()
    assert detail["exists_on_disk"] and detail["relative_path"].startswith("processed/DB101")
    assert "SQL" in detail["text_preview"]
    assert detail["telegram_link"] == "https://t.me/test_channel/7"
    assert [x["stage"] for x in detail["logs"]] == ["extract", "classify", "move"]

    dl = auth.get(f"/api/v1/files/{f.id}/download")
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF")

    r = auth.post(f"/api/v1/files/{f.id}/classify",
                  json={"subject_code": "CS101", "content_type": "summary"})
    assert r.status_code == 200
    assert r.json()["classification"]["classifier_version"] == "manual"
    assert auth.post(f"/api/v1/files/{f.id}/classify",
                     json={"subject_code": "NOPE1", "content_type": "summary"}
                     ).status_code == 422
    assert auth.post(f"/api/v1/files/{f.id}/classify",
                     json={"subject_code": "CS101", "content_type": "video"}).status_code == 422
    assert auth.get("/api/v1/files/99999").status_code == 404


def test_file_actions_blocked_while_locked(auth: TestClient, settings: Settings, db: Session,
                                           channel: Channel, subjects: list[Subject]) -> None:
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)
    p = make_pdf(settings.incoming_dir / "a.pdf", ["x"])
    f = make_file(db, channel, p, name="a.pdf", msg_id=1)
    with JobLock(settings.lock_path, kind="collect", trigger="launchd"):
        assert auth.post(f"/api/v1/files/{f.id}/reprocess").status_code == 423


def test_download_refuses_paths_outside_storage(auth: TestClient, db: Session,
                                                channel: Channel) -> None:
    f = make_file(db, channel, Path("/etc/hosts"), name="hosts.pdf", msg_id=1)
    assert auth.get(f"/api/v1/files/{f.id}/download").status_code == 404


def test_overview_messages_runs_report(auth: TestClient, db: Session, channel: Channel,
                                       subjects: list[Subject]) -> None:
    make_file(db, channel, None, name="a.pdf", msg_id=1, status=FileStatus.FAILED)
    ov = auth.get("/api/v1/overview").json()
    kpis = {k["key"]: k for k in ov["kpis"]}
    assert kpis["total"]["value"] == 1 and kpis["failed"]["value"] == 1
    assert len(kpis["total"]["sparkline"]) == 14 and len(ov["daily"]) == 30
    assert ov["daily"][-1]["total"] == 1
    assert {e["code"] for e in ov["empty_subjects"]} == {"DB101", "CS101"}
    assert len(ov["recent_files"]) == 1
    msgs = auth.get("/api/v1/messages").json()
    assert msgs["total"] == 1 and msgs["items"][0]["file_status"] == "failed"
    assert auth.get("/api/v1/runs").json()["total"] == 0
    assert auth.get("/api/v1/report").json()["failed"] == 1
    status = auth.get("/api/v1/system/status").json()
    assert status["db"] is True and status["lock"]["locked"] is False
    health = auth.get("/api/v1/system/health").json()
    assert {c["key"] for c in health["checks"]} >= {"mysql", "tesseract", "telegram", "openai"}


def test_settings_never_expose_secrets(auth: TestClient, settings: Settings) -> None:
    body = auth.get("/api/v1/settings").text
    for secret in (TEST_PASSWORD, settings.session_secret.get_secret_value(),  # type: ignore[union-attr]
                   "0123456789abcdef0123456789abcdef", "tuc_test"):
        assert secret not in body
    data = json.loads(body)["sections"]
    db_url = next(r for r in data["database"] if r["key"] == "database_url")
    assert db_url == {"key": "database_url", "secret": True, "configured": True, "value": None}


def test_settings_actions(auth: TestClient) -> None:
    r = auth.post("/api/v1/settings/seed-demo")
    assert r.status_code == 200 and r.json()["files"] > 50
    assert auth.post("/api/v1/settings/seed-demo").json() == {"skipped": 1}
    r = auth.post("/api/v1/settings/import-config")
    assert r.status_code == 200 and "subjects" in r.json()
    up = auth.post("/api/v1/settings/import-config", files={
        "subjects": ("s.yaml", b"subjects:\n  - {code: PHY1, name_ar: x, name_en: y}\n")})
    assert up.json()["subjects"]["created"] == 1
    bad = auth.post("/api/v1/settings/import-config", files={"subjects": ("s.yaml", b"[: bad")})
    assert bad.status_code == 422
    z = auth.get("/api/v1/settings/export-config")
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert sorted(names) == ["channels.yaml", "subjects.yaml"]
    assert auth.post("/api/v1/settings/test-openai").json()["ok"] is False
    assert auth.get("/api/v1/runs").json()["total"] > 0
    run_id = auth.get("/api/v1/runs").json()["items"][0]["id"]
    assert auth.get(f"/api/v1/runs/{run_id}").status_code == 200


# ------------------------------------------------------------------ jobs
def _wait(auth: TestClient, job_id: str, timeout: float = 60) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job: dict[str, Any] = auth.get(f"/api/v1/jobs/{job_id}").json()
        if job["state"] not in ("queued", "running"):
            return job
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_process_job_runs_cli_and_streams(auth: TestClient, settings: Settings, db: Session,
                                          channel: Channel, subjects: list[Subject]) -> None:
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)
    p = make_pdf(settings.incoming_dir / "a.pdf", ["Database SQL lecture"])
    make_file(db, channel, p, name="DB101 lecture 1.pdf", msg_id=1)
    r = auth.post("/api/v1/jobs", json={"kind": "process"})
    assert r.status_code == 202
    job = _wait(auth, r.json()["id"])
    assert job["state"] == "succeeded", job
    assert job["run_id"] is not None and job["counters"].get("classified") == 1

    with auth.stream("GET", f"/api/v1/jobs/{job['id']}/stream") as s:
        assert s.headers["content-type"].startswith("text/event-stream")
        body = "".join(s.iter_text())
    assert "event: log" in body and "event: end" in body and "run_started" in body

    run = auth.get(f"/api/v1/runs/{job['run_id']}").json()
    assert run["trigger"] == "web" and run["classified_count"] == 1
    assert any(line["event"] == "run_finished" for line in run["log_lines"])


def test_job_conflict_when_locked(auth: TestClient, settings: Settings) -> None:
    with JobLock(settings.lock_path, kind="collect", trigger="launchd"):
        lock = auth.get("/api/v1/jobs/lock").json()
        assert lock["locked"] and lock["holder"]["trigger"] == "launchd"
        r = auth.post("/api/v1/jobs", json={"kind": "process"})
        assert r.status_code == 409
        assert r.json()["detail"]["holder"]["kind"] == "collect"
    assert auth.get("/api/v1/jobs/lock").json()["locked"] is False


def test_job_validation(auth: TestClient) -> None:
    assert auth.post("/api/v1/jobs", json={"kind": "rm -rf"}).status_code == 422
    assert auth.post("/api/v1/jobs", json={"kind": "process", "limit": 0}).status_code == 422
    assert auth.get("/api/v1/jobs/nope").status_code == 404
