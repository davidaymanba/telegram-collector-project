"""TUC command line: `python -m app.cli <command>`."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from app.config import get_settings
from app.config.loaders import ConfigError, load_channels, load_subjects
from app.database.enums import FileStatus, RunKind, RunTrigger
from app.logging import configure_logging, get_logger
from app.runtime.lock import EXIT_LOCKED, LockBusyError

app = typer.Typer(
    name="tuc",
    help="Telegram University Content Collector",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)
launchd_app = typer.Typer(help="Manage macOS LaunchAgents (background scheduling).",
                          no_args_is_help=True)
app.add_typer(launchd_app, name="launchd")

console = Console()
err = Console(stderr=True)
log = get_logger("tuc.cli")

STATUS_STYLE = {"ok": "[green]✓ ok[/]", "warn": "[yellow]! warn[/]", "fail": "[red]✗ fail[/]"}
TriggerOpt = Annotated[RunTrigger, typer.Option("--trigger", hidden=True)]


@app.callback()
def _main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    settings = get_settings()
    configure_logging("DEBUG" if verbose else settings.log_level, settings.effective_log_format)


def _fail(message: str, code: int = 1) -> typer.Exit:
    err.print(f"[bold red]✗[/] {message}")
    return typer.Exit(code)


def _locked(exc: LockBusyError) -> typer.Exit:
    err.print(f"[bold yellow]⏳ {exc}[/]")
    log.warning("lock_busy", holder=exc.holder)
    return typer.Exit(EXIT_LOCKED)


def _counters_table(title: str, counters: dict[str, int]) -> Table:
    table = Table(title=title, show_header=False, title_justify="left")
    for key in ("new", "duplicate", "classified", "unclassified", "failed", "unsupported"):
        if key in counters or key in ("new", "classified"):
            table.add_row(key, f"[bold]{counters.get(key, 0)}[/]")
    return table


# ---------------------------------------------------------------------------- setup
@app.command("health-check")
def health_check(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Check MySQL, Tesseract, Telegram session, OpenAI, storage, permissions and launchd."""
    from app.runtime.health import run_health_checks

    checks = run_health_checks(get_settings())
    if as_json:
        console.print_json(json.dumps([c.as_dict() for c in checks], default=str))
    else:
        table = Table(title="TUC health check", title_justify="left")
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Detail", overflow="fold")
        for c in checks:
            table.add_row(c.key, STATUS_STYLE[c.status], c.detail)
        console.print(table)
    if any(c.status == "fail" for c in checks if c.key in ("mysql",)):
        raise typer.Exit(1)


@app.command("init-db")
def init_db(
    import_config_files: Annotated[bool, typer.Option("--import-config/--no-import-config")] = True,
) -> None:
    """Run migrations, create storage folders and import YAML seeds into an empty database."""
    from app.database.migrate import upgrade_head
    from app.database.repositories import ChannelRepository, SubjectRepository
    from app.database.session import session_scope
    from app.storage.paths import StorageLayout

    settings = get_settings()
    try:
        upgrade_head()
    except Exception as exc:
        raise _fail(f"Migration failed: {exc}") from exc
    StorageLayout(settings).ensure()
    console.print("[green]✓[/] Database schema is up to date")
    console.print(f"[green]✓[/] Storage ready at {settings.storage_root}")
    if import_config_files:
        with session_scope() as s:
            empty = not SubjectRepository(s).list_all() and not ChannelRepository(s).list_all()
        if empty:
            _import(settings.subjects_config_path, settings.channels_config_path)


# ---------------------------------------------------------------------------- telegram
@app.command("telegram-login")
def telegram_login() -> None:
    """Interactive Telegram login (phone → code → optional 2FA). Creates the session file."""
    from app.telegram.gateway import CredentialsMissingError
    from app.telegram.telethon_gateway import build_client, secure_session_file

    settings = get_settings()
    try:
        client = build_client(settings)
    except CredentialsMissingError as exc:
        raise _fail(str(exc), 2) from exc

    async def _login() -> str:
        await client.start()  # prompts for phone, code and password as needed
        me = await client.get_me()
        await client.disconnect()
        return str(getattr(me, "username", None) or getattr(me, "first_name", "user"))

    user = asyncio.run(_login())
    secure_session_file(settings)
    console.print(f"[green]✓[/] Logged in as [bold]{user}[/]. Session: "
                  f"{settings.telegram_session_file} (mode 600)")


@app.command()
def collect(
    channel: Annotated[str | None, typer.Option("--channel", "-c",
                                                help="Channel id, @username or name")] = None,
    limit: Annotated[int | None, typer.Option("--limit", "-n", min=1,
                                              help="Max messages per channel")] = None,
    trigger: TriggerOpt = RunTrigger.CLI,
) -> None:
    """Collect new files from enabled Telegram channels."""
    from app.database.session import session_scope
    from app.runtime.runs import tracked_run
    from app.telegram.collector import Collector
    from app.telegram.gateway import CredentialsMissingError, NotAuthorizedError, TelegramError
    from app.telegram.telethon_gateway import TelethonGateway

    settings = get_settings()
    if not settings.telegram_configured:
        raise _fail("Telegram credentials missing (TUC_TELEGRAM_API_ID / TUC_TELEGRAM_API_HASH)", 2)
    try:
        with tracked_run(settings, RunKind.COLLECT, trigger,
                         {"channel": channel, "limit": limit}) as run, session_scope() as s:
            collector = Collector(settings, s, TelethonGateway(settings), run=run)
            summary = asyncio.run(collector.collect(channel, limit))
    except LockBusyError as exc:
        raise _locked(exc) from exc
    except (CredentialsMissingError, NotAuthorizedError) as exc:
        raise _fail(str(exc), 2) from exc
    except TelegramError as exc:
        raise _fail(str(exc)) from exc
    console.print(_counters_table(f"Collect run #{run.run_id}", dict(run.counters)))
    for e in summary.errors:
        err.print(f"[red]•[/] {e}")
    if summary.errors and len(summary.errors) == len(summary.channels):
        raise typer.Exit(1)


# ---------------------------------------------------------------------------- processing
@app.command()
def process(
    limit: Annotated[int | None, typer.Option("--limit", "-n", min=1)] = None,
    file_id: Annotated[list[int] | None, typer.Option("--file-id", help="Only these files")] = None,
    retry_failed: Annotated[bool, typer.Option("--retry-failed")] = False,
    trigger: TriggerOpt = RunTrigger.CLI,
) -> None:
    """Extract text, classify and file away downloaded files."""
    from app.database.session import session_scope
    from app.processing.pipeline import Processor
    from app.runtime.runs import tracked_run

    settings = get_settings()
    try:
        with tracked_run(settings, RunKind.PROCESS, trigger,
                         {"limit": limit, "file_ids": file_id}) as run, session_scope() as s:
            Processor(settings, s).process_pending(limit=limit, run=run, file_ids=file_id,
                                                   include_failed=retry_failed)
    except LockBusyError as exc:
        raise _locked(exc) from exc
    console.print(_counters_table(f"Process run #{run.run_id}", dict(run.counters)))


@app.command()
def reclassify(
    status: Annotated[list[FileStatus] | None, typer.Option("--status")] = None,
    limit: Annotated[int | None, typer.Option("--limit", "-n", min=1)] = None,
    trigger: TriggerOpt = RunTrigger.CLI,
) -> None:
    """Re-run classification on already-extracted text (default: unclassified files)."""
    from app.database.session import session_scope
    from app.processing.pipeline import Processor
    from app.runtime.runs import tracked_run

    settings = get_settings()
    statuses = status or [FileStatus.UNCLASSIFIED]
    try:
        with tracked_run(settings, RunKind.PROCESS, trigger,
                         {"reclassify": [s.value for s in statuses]}) as run, \
                session_scope() as s:
            Processor(settings, s).reclassify(statuses=statuses, limit=limit, run=run)
    except LockBusyError as exc:
        raise _locked(exc) from exc
    console.print(_counters_table(f"Reclassify run #{run.run_id}", dict(run.counters)))


@app.command()
def report(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Summary of collected files by status, subject and content type."""
    from app.database.session import session_scope
    from app.reports.reporter import build_report, format_report

    with session_scope() as s:
        rep = build_report(s)
    if as_json:
        sys.stdout.write(json.dumps(rep.as_dict(), ensure_ascii=False, indent=2) + "\n")
    else:
        console.print(format_report(rep), highlight=False)


# ---------------------------------------------------------------------------- config
def _import(subjects_path: Path | None, channels_path: Path | None) -> dict[str, Any]:
    from app.database.session import session_scope
    from app.ingestion.config_sync import import_channels, import_subjects

    out: dict[str, Any] = {}
    with session_scope() as s:
        if subjects_path:
            out["subjects"] = import_subjects(s, load_subjects(subjects_path)).as_dict()
            console.print(f"[green]✓[/] Subjects from {subjects_path.name}: {out['subjects']}")
        if channels_path:
            if channels_path.exists():
                out["channels"] = import_channels(s, load_channels(channels_path)).as_dict()
                console.print(f"[green]✓[/] Channels from {channels_path.name}: {out['channels']}")
            else:
                console.print(f"[yellow]![/] {channels_path} not found — skipped")
    return out


@app.command("import-config")
def import_config(
    subjects: Annotated[Path | None, typer.Option(help="subjects.yaml")] = None,
    channels: Annotated[Path | None, typer.Option(help="channels.yaml")] = None,
) -> None:
    """Import subjects and channels from YAML into the database (upsert)."""
    settings = get_settings()
    try:
        _import(subjects or settings.subjects_config_path, channels or settings.channels_config_path)
    except ConfigError as exc:
        raise _fail(str(exc)) from exc


@app.command("export-config")
def export_config(
    out_dir: Annotated[Path, typer.Option("--out-dir", help="Where to write the YAML files")] = Path(
        "config/export"),
) -> None:
    """Export subjects and channels from the database to YAML."""
    from app.database.session import session_scope
    from app.ingestion.config_sync import export_channels, export_subjects

    out_dir.mkdir(parents=True, exist_ok=True)
    with session_scope() as s:
        (out_dir / "subjects.yaml").write_text(export_subjects(s), encoding="utf-8")
        (out_dir / "channels.yaml").write_text(export_channels(s), encoding="utf-8")
    console.print(f"[green]✓[/] Exported to {out_dir}/subjects.yaml and channels.yaml")


@app.command("seed-demo")
def seed_demo_cmd(
    reset: Annotated[bool, typer.Option("--reset", help="Replace existing demo data")] = False,
) -> None:
    """Insert realistic demo data (channels, files, runs) to explore the dashboard."""
    from app.database.session import session_scope
    from app.ingestion.seed import seed_demo

    settings = get_settings()
    with session_scope() as s:
        result = seed_demo(s, settings, reset=reset)
    if result.get("skipped"):
        console.print("[yellow]![/] Demo data already present (use --reset to recreate)")
    else:
        console.print(f"[green]✓[/] Demo data created: {result}")


# ---------------------------------------------------------------------------- web
@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
    reload: Annotated[bool, typer.Option("--reload")] = False,
) -> None:
    """Run the dashboard + API (serves the built frontend from frontend/dist)."""
    import uvicorn

    if host not in ("127.0.0.1", "localhost", "::1"):
        err.print(f"[yellow]![/] Listening on {host} exposes the dashboard to the network. "
                  "Put it behind HTTPS (see deploy/nginx) and set TUC_APP_ENV=production.")
    console.print(f"[green]➜[/] Dashboard: [link]http://{host}:{port}[/link]")
    uvicorn.run("app.web.app:create_app", factory=True, host=host, port=port, reload=reload,
                proxy_headers=False, server_header=False, log_config=None)


@app.command("hash-password")
def hash_password(password: Annotated[str, typer.Option(prompt=True, hide_input=True,
                                                        confirmation_prompt=True)]) -> None:
    """Print an argon2 hash to use as DASHBOARD_PASSWORD (so the plain password is never stored)."""
    from app.web.auth.security import hash_password as _hash

    sys.stdout.write(_hash(password) + "\n")


# ---------------------------------------------------------------------------- launchd
@launchd_app.command("install")
def launchd_install(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
) -> None:
    """Generate plists, copy them to ~/Library/LaunchAgents and load them."""
    from app.runtime.launchd import LaunchdManager, venv_python

    if sys.platform != "darwin":
        raise _fail("launchd is macOS only — see deploy/linux for systemd units")
    if not (Path(venv_python()).exists()):
        raise _fail("Python venv not found — run `uv sync` first")
    for line in LaunchdManager(get_settings()).install(host=host, port=port):
        console.print(f"  {line}")
    console.print("[green]✓[/] LaunchAgents installed. Logs: ~/Library/Logs/tuc/")


@launchd_app.command("uninstall")
def launchd_uninstall() -> None:
    """Unload and remove the TUC LaunchAgents."""
    from app.runtime.launchd import LaunchdManager

    for line in LaunchdManager(get_settings()).uninstall():
        console.print(f"  {line}")


@launchd_app.command("status")
def launchd_status() -> None:
    """Show whether each LaunchAgent is installed/loaded and its last exit code."""
    from app.runtime.launchd import LaunchdManager

    table = Table(title="LaunchAgents", title_justify="left")
    for col in ("Label", "Installed", "Loaded", "State", "PID", "Last exit"):
        table.add_column(col)
    for a in LaunchdManager(get_settings()).status():
        table.add_row(a.label, "✓" if a.installed else "—", "✓" if a.loaded else "—",
                      a.state or "—", str(a.pid or "—"),
                      "—" if a.last_exit_code is None else str(a.last_exit_code))
    console.print(table)


def main() -> None:
    os.umask(0o077)  # files we create (texts, downloads, session) are private by default
    app()
