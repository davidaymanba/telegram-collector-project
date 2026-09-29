from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.runtime.launchd import LABELS, LaunchdManager, PlistContext, render_plist


@pytest.fixture
def ctx(tmp_path: Path) -> PlistContext:
    return PlistContext(
        python=Path("/Users/me/My Projects/tuc & co/.venv/bin/python"),
        project_dir=Path("/Users/me/My Projects/tuc & co"),
        log_dir=tmp_path / "Logs" / "tuc",
        collect_interval_minutes=30,
        process_interval_minutes=15,
        path_env="/opt/homebrew/bin:/usr/bin",
    )


@pytest.mark.parametrize("name", list(LABELS))
def test_rendered_plists_are_valid(name: str, ctx: PlistContext) -> None:
    data = plistlib.loads(render_plist(name, ctx).encode())
    assert data["Label"] == LABELS[name]
    args = data["ProgramArguments"]
    assert args[0] == str(ctx.python)            # absolute path, spaces and '&' preserved
    assert args[1:3] == ["-m", "app.cli"]
    assert data["WorkingDirectory"] == str(ctx.project_dir)
    assert data["StandardOutPath"].startswith(str(ctx.log_dir))
    assert data["StandardErrorPath"].startswith(str(ctx.log_dir))
    assert Path(data["StandardOutPath"]).is_absolute()
    assert data["EnvironmentVariables"]["PATH"] == "/opt/homebrew/bin:/usr/bin"


def test_web_agent_keepalive(ctx: PlistContext) -> None:
    data = plistlib.loads(render_plist("web", ctx).encode())
    assert data["KeepAlive"] is True and data["RunAtLoad"] is True
    assert data["ProgramArguments"][3:] == ["serve", "--host", "127.0.0.1", "--port", "8000"]


def test_interval_agents(ctx: PlistContext) -> None:
    collector = plistlib.loads(render_plist("collector", ctx).encode())
    process = plistlib.loads(render_plist("process", ctx).encode())
    assert collector["StartInterval"] == 30 * 60
    assert process["StartInterval"] == 15 * 60
    assert collector["ProgramArguments"][3:] == ["collect", "--trigger", "launchd"]
    assert process["ProgramArguments"][3:] == ["process", "--trigger", "launchd"]
    assert "KeepAlive" not in collector


def test_install_status_uninstall_with_fake_launchctl(settings: Settings, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    loaded: set[str] = set()

    def runner(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        action = cmd[1]
        if action == "bootstrap":
            loaded.add(Path(cmd[3]).stem)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if action == "bootout":
            loaded.discard(cmd[2].rsplit("/", 1)[-1])
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if action == "print":
            label = cmd[2].rsplit("/", 1)[-1]
            if label in loaded:
                return subprocess.CompletedProcess(cmd, 0,
                    "\tstate = not running\n\tlast exit code = 0\n", "")
            return subprocess.CompletedProcess(cmd, 113, "", "not found")
        raise AssertionError(cmd)

    agents = tmp_path / "LaunchAgents"
    mgr = LaunchdManager(settings, agents_dir=agents, log_dir=tmp_path / "logs", runner=runner)
    messages = mgr.install()
    assert all("loaded" in m for m in messages)
    for label in LABELS.values():
        plist = agents / f"{label}.plist"
        assert plist.exists()
        plistlib.loads(plist.read_bytes())
    assert any(c[1] == "bootstrap" and c[2].startswith("gui/") for c in calls)
    statuses = mgr.status()
    assert all(s.installed and s.loaded and s.last_exit_code == 0 for s in statuses)

    mgr.uninstall()
    assert not list(agents.glob("*.plist"))
    assert not any(s.loaded or s.installed for s in mgr.status())
