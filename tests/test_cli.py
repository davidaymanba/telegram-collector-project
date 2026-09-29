from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app.cli.main import app
from app.config import Settings
from app.database.models import Channel, Subject
from app.reports.reporter import build_report, format_report
from app.runtime.lock import EXIT_LOCKED, JobLock
from tests.conftest import make_file
from tests.factories import make_pdf

runner = CliRunner()
ROOT = Path(__file__).parents[1]


def test_help_lists_commands() -> None:
    out = runner.invoke(app, ["--help"]).output
    for cmd in ("health-check", "init-db", "telegram-login", "collect", "process", "reclassify",
                "report", "import-config", "export-config", "serve", "seed-demo", "launchd"):
        assert cmd in out


def test_import_export_and_report_json(settings: Settings, tmp_path: Path) -> None:
    r = runner.invoke(app, ["import-config"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["export-config", "--out-dir", str(tmp_path / "exp")])
    assert r.exit_code == 0
    assert "DB101" in (tmp_path / "exp" / "subjects.yaml").read_text(encoding="utf-8")
    r = runner.invoke(app, ["report", "--json"])
    data = json.loads(r.stdout)
    assert data["total"] == 0 and set(data["empty_subjects"]) == {"DB101", "CS101"}


def test_seed_demo_and_text_report(settings: Settings, db: Session) -> None:
    assert runner.invoke(app, ["seed-demo"]).exit_code == 0
    assert "already present" in runner.invoke(app, ["seed-demo"]).output
    assert runner.invoke(app, ["seed-demo", "--reset"]).exit_code == 0
    report = build_report(db)
    assert report.total >= 100 and report.classified > 0 and report.empty_subjects
    text = format_report(report)
    assert "By subject" in text and "Subjects with no content" in text


def test_process_command(settings: Settings, db: Session, channel: Channel,
                         subjects: list[Subject]) -> None:
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)
    p = make_pdf(settings.incoming_dir / "a.pdf", ["CS101 algorithms lecture"])
    make_file(db, channel, p, name="CS101 Lecture 2.pdf", msg_id=1)
    r = runner.invoke(app, ["process"])
    assert r.exit_code == 0, r.output
    assert "classified" in r.output


def test_reclassify_command(settings: Settings) -> None:
    r = runner.invoke(app, ["reclassify", "--status", "unclassified"])
    assert r.exit_code == 0, r.output


def test_process_exits_75_when_locked(settings: Settings) -> None:
    with JobLock(settings.lock_path, kind="collect", trigger="launchd"):
        r = runner.invoke(app, ["process"])
    assert r.exit_code == EXIT_LOCKED
    assert "already running" in r.output


def test_collect_without_credentials(settings: Settings) -> None:
    settings.telegram_api_id = None
    r = runner.invoke(app, ["collect"])
    assert r.exit_code == 2 and "credentials" in r.output


def test_health_check_json(settings: Settings) -> None:
    r = runner.invoke(app, ["health-check", "--json"])
    assert r.exit_code == 0, r.output
    keys = {c["key"] for c in json.loads(r.stdout)}
    expected = {"mysql", "tesseract", "telegram", "openai", "storage", "permissions", "lock"}
    if sys.platform == "darwin":
        expected.add("launchd")
    assert expected <= keys


def test_module_entrypoint_runs(settings: Settings) -> None:
    """`python -m app.cli` works as a real subprocess (as launchd runs it)."""
    out = subprocess.run([sys.executable, "-m", "app.cli", "report", "--json"], cwd=ROOT,
                         capture_output=True, text=True, check=False, timeout=60)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["total"] == 0


def test_hash_password() -> None:
    r = runner.invoke(app, ["hash-password"], input="pw\npw\n")
    assert r.exit_code == 0 and "$argon2" in r.output
