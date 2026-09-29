"""structlog configuration: JSON in production (and for web-spawned jobs), readable console otherwise."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, Literal

import structlog

_SECRET_KEYS = re.compile(r"(api_hash|api_key|password|secret|token|authorization|cookie)", re.I)
_URL_PASSWORD = re.compile(r"(://[^:/@\s]+:)([^@\s]+)(@)")


def _redact(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Never let secrets reach log output."""
    for key in list(event_dict):
        if _SECRET_KEYS.search(key):
            event_dict[key] = "***"
        elif isinstance(event_dict[key], str):
            event_dict[key] = _URL_PASSWORD.sub(r"\1***\3", event_dict[key])
    return event_dict


def configure_logging(
    level: str = "INFO",
    fmt: Literal["json", "console"] = "console",
    log_file: Path | None = None,
) -> None:
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: Any = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    handlers: list[logging.Handler] = []
    stream = logging.StreamHandler(sys.stdout if fmt == "json" else sys.stderr)
    stream.setFormatter(
        structlog.stdlib.ProcessorFormatter(processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer
        ], foreign_pre_chain=shared)
    )
    handlers.append(stream)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(
            structlog.stdlib.ProcessorFormatter(processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(ensure_ascii=False),
            ], foreign_pre_chain=shared)
        )
        handlers.append(fh)

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()
    for h in handlers:
        root.addHandler(h)
    root.setLevel(level)
    for noisy in ("telethon", "httpx", "openai", "multipart", "PIL"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )


def add_file_handler(log_file: Path) -> logging.Handler:
    """Attach an extra JSON-lines file (used for per-run logs); returns it for later removal."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ])
    )
    logging.getLogger().addHandler(handler)
    return handler


def remove_handler(handler: logging.Handler) -> None:
    logging.getLogger().removeHandler(handler)
    handler.close()


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)
