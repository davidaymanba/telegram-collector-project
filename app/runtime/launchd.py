"""Generate, install and inspect the launchd LaunchAgents that run TUC in the background.

Templates live in `deploy/launchd/`; placeholders are substituted with XML-escaped absolute
paths (the project path may contain spaces) and the result is validated with `plistlib`.
"""

from __future__ import annotations

import os
import plistlib
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from app.config import PROJECT_ROOT, Settings

TEMPLATE_DIR = PROJECT_ROOT / "deploy" / "launchd"
LABELS = {"web": "com.tuc.web", "collector": "com.tuc.collector", "process": "com.tuc.process"}
DEFAULT_LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
DEFAULT_LOG_DIR = Path.home() / "Library" / "Logs" / "tuc"

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)


def venv_python() -> Path:
    candidate = PROJECT_ROOT / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def default_path_env() -> str:
    parts = [str(venv_python().parent), "/opt/homebrew/bin", "/usr/local/bin",
             "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    return ":".join(dict.fromkeys(parts))


@dataclass(slots=True)
class PlistContext:
    python: Path
    project_dir: Path
    log_dir: Path
    host: str = "127.0.0.1"
    port: int = 8000
    collect_interval_minutes: int = 30
    process_interval_minutes: int = 15
    path_env: str = ""

    @classmethod
    def from_settings(cls, settings: Settings, *, host: str = "127.0.0.1", port: int = 8000,
                      log_dir: Path | None = None) -> PlistContext:
        return cls(
            python=venv_python(),
            project_dir=PROJECT_ROOT,
            log_dir=log_dir or DEFAULT_LOG_DIR,
            host=host,
            port=port,
            collect_interval_minutes=settings.collect_interval_minutes,
            process_interval_minutes=settings.process_interval_minutes,
            path_env=default_path_env(),
        )


def render_plist(name: str, ctx: PlistContext) -> str:
    template = (TEMPLATE_DIR / f"{LABELS[name]}.plist").read_text(encoding="utf-8")
    interval = ctx.collect_interval_minutes if name == "collector" else ctx.process_interval_minutes
    values = {
        "PYTHON": str(ctx.python),
        "PROJECT_DIR": str(ctx.project_dir),
        "LOG_DIR": str(ctx.log_dir),
        "HOST": ctx.host,
        "PORT": str(ctx.port),
        "PATH": ctx.path_env or default_path_env(),
        "INTERVAL_SECONDS": str(int(interval) * 60),
    }
    rendered = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: escape(values[m.group(1)]), template)
    plistlib.loads(rendered.encode("utf-8"))  # raises if the XML is invalid
    return rendered


@dataclass(slots=True)
class AgentStatus:
    name: str
    label: str
    installed: bool
    loaded: bool
    state: str | None = None
    pid: int | None = None
    last_exit_code: int | None = None
    plist_path: str | None = None


class LaunchdManager:
    def __init__(self, settings: Settings, *, agents_dir: Path | None = None,
                 log_dir: Path | None = None, runner: Runner = _run) -> None:
        self.settings = settings
        self.agents_dir = agents_dir or DEFAULT_LAUNCH_AGENTS
        self.log_dir = log_dir or DEFAULT_LOG_DIR
        self.runner = runner
        self.domain = f"gui/{os.getuid()}"

    def plist_path(self, name: str) -> Path:
        return self.agents_dir / f"{LABELS[name]}.plist"

    def install(self, *, host: str = "127.0.0.1", port: int = 8000,
                names: tuple[str, ...] = tuple(LABELS)) -> list[str]:
        ctx = PlistContext.from_settings(self.settings, host=host, port=port, log_dir=self.log_dir)
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        messages: list[str] = []
        for name in names:
            path = self.plist_path(name)
            path.write_text(render_plist(name, ctx), encoding="utf-8")
            os.chmod(path, 0o644)
            label = LABELS[name]
            self.runner(["launchctl", "bootout", f"{self.domain}/{label}"])  # ignore if absent
            res = self.runner(["launchctl", "bootstrap", self.domain, str(path)])
            ok = res.returncode == 0
            messages.append(f"{label}: {'loaded' if ok else 'bootstrap failed: ' + res.stderr.strip()}")
        return messages

    def uninstall(self, names: tuple[str, ...] = tuple(LABELS)) -> list[str]:
        messages: list[str] = []
        for name in names:
            label = LABELS[name]
            self.runner(["launchctl", "bootout", f"{self.domain}/{label}"])
            path = self.plist_path(name)
            existed = path.exists()
            path.unlink(missing_ok=True)
            messages.append(f"{label}: {'removed' if existed else 'not installed'}")
        return messages

    def status(self) -> list[AgentStatus]:
        out: list[AgentStatus] = []
        for name, label in LABELS.items():
            path = self.plist_path(name)
            st = AgentStatus(name=name, label=label, installed=path.exists(), loaded=False,
                             plist_path=str(path))
            try:
                res = self.runner(["launchctl", "print", f"{self.domain}/{label}"])
            except (OSError, subprocess.TimeoutExpired):
                res = None
            if res is not None and res.returncode == 0:
                st.loaded = True
                if m := re.search(r"^\s*state = (\S+)", res.stdout, re.M):
                    st.state = m.group(1)
                if m := re.search(r"^\s*pid = (\d+)", res.stdout, re.M):
                    st.pid = int(m.group(1))
                if m := re.search(r"last exit code = (-?\d+)", res.stdout):
                    st.last_exit_code = int(m.group(1))
            out.append(st)
        return out
