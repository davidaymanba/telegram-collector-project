"""Dashboard authentication: argon2 password check, signed session cookie, CSRF, login throttle."""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import Settings

_hasher = PasswordHasher()
CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "tuc_csrf"
SESSION_COOKIE = "tuc_session"


def hash_password(password: str) -> str:
    return str(_hasher.hash(password))


def is_argon2_hash(value: str) -> bool:
    return value.startswith("$argon2")


@lru_cache(maxsize=4)
def _password_hash_for(raw: str) -> str:
    """DASHBOARD_PASSWORD may be an argon2 hash (recommended) or plain text.

    Plain text is hashed once in memory at startup and only the hash is ever compared, so the
    plain value is never persisted or logged by the app.
    """
    return raw if is_argon2_hash(raw) else hash_password(raw)


def password_hash(settings: Settings) -> str | None:
    if settings.dashboard_password is None:
        return None
    raw = settings.dashboard_password.get_secret_value()
    return _password_hash_for(raw) if raw else None


def verify_credentials(settings: Settings, username: str, password: str) -> bool:
    expected = password_hash(settings)
    user_ok = hmac.compare_digest(username.encode(), settings.dashboard_username.encode())
    if expected is None:
        return False
    try:
        pw_ok = bool(_hasher.verify(expected, password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pw_ok = False
    return user_ok and pw_ok


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_matches(expected: str | None, provided: str | None) -> bool:
    return bool(expected and provided and hmac.compare_digest(expected, provided))


class LoginThrottle:
    """Sliding-window limiter per client IP (in-memory; the server is single-process)."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def retry_after(self, key: str) -> int:
        with self._lock:
            now = time.monotonic()
            q = self._prune(key, now)
            if len(q) < self.max_attempts:
                return 0
            return max(1, int(self.window - (now - q[0])))

    def failure(self, key: str) -> None:
        with self._lock:
            self._prune(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)
