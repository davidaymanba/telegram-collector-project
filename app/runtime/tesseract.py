from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

HOMEBREW_CANDIDATES = ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract")


def find_tesseract(configured: str | None = None) -> str | None:
    """Explicit setting → PATH → Apple Silicon Homebrew → Intel Homebrew."""
    if configured:
        return configured if Path(configured).is_file() else None
    if found := shutil.which("tesseract"):
        return found
    for candidate in HOMEBREW_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


@lru_cache(maxsize=4)
def tesseract_languages(cmd: str) -> tuple[str, ...]:
    try:
        out = subprocess.run(
            [cmd, "--list-langs"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    lines = (out.stdout or out.stderr).splitlines()
    return tuple(line.strip() for line in lines[1:] if line.strip())


def tesseract_version(cmd: str) -> str | None:
    try:
        out = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=10,
                             check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    first = (out.stdout or out.stderr).splitlines()
    return first[0].strip() if first else None


def missing_languages(cmd: str, spec: str) -> list[str]:
    have = set(tesseract_languages(cmd))
    return [lang for lang in spec.split("+") if lang and lang not in have]
