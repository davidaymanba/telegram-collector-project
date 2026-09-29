from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from app.runtime.lock import JobLock, LockBusyError, lock_status


def test_acquire_release(tmp_path: Path) -> None:
    path = tmp_path / "x.lock"
    assert not lock_status(path).locked
    with JobLock(path, kind="collect", trigger="cli") as lock:
        assert lock.held
        st = lock_status(path)
        assert st.locked
        assert st.holder is not None
        assert st.holder["kind"] == "collect" and st.holder["pid"] == os.getpid()
    assert not lock_status(path).locked
    assert oct(path.stat().st_mode & 0o777) == oct(0o600)


def test_second_lock_in_same_process_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "x.lock"
    with JobLock(path, kind="process", trigger="launchd"):
        with pytest.raises(LockBusyError) as exc:
            JobLock(path, kind="collect").acquire()
        assert exc.value.holder is not None
        assert exc.value.holder["trigger"] == "launchd"
        assert "already running" in str(exc.value)


def test_lock_is_exclusive_across_processes(tmp_path: Path) -> None:
    path = tmp_path / "x.lock"
    code = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        from app.runtime.lock import JobLock, LockBusyError
        try:
            JobLock(Path({str(path)!r})).acquire()
        except LockBusyError:
            sys.exit(75)
        sys.exit(0)
    """)
    root = Path(__file__).parents[1]
    with JobLock(path):
        busy = subprocess.run([sys.executable, "-c", code], cwd=root, check=False)
    assert busy.returncode == 75
    free = subprocess.run([sys.executable, "-c", code], cwd=root, check=False)
    assert free.returncode == 0


def test_lock_released_when_holder_dies(tmp_path: Path) -> None:
    path = tmp_path / "x.lock"
    code = textwrap.dedent(f"""
        import os
        from pathlib import Path
        from app.runtime.lock import JobLock
        JobLock(Path({str(path)!r})).acquire()
        os._exit(1)  # crash without releasing
    """)
    subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parents[1], check=False)
    assert not lock_status(path).locked
    with JobLock(path):
        pass
