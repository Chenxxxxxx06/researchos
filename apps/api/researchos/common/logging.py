"""Structured logging configuration.

Uses structlog to emit JSON logs (or a human-friendly console renderer when
``LOG_JSON=false``). A ``request_id`` is bound via contextvars by the request
middleware and automatically attached to every log line, so a request can be
traced across API -> Redis -> worker boundaries.

Secrets must never be passed to the logger.
"""

from __future__ import annotations

import logging
import sys

import structlog

from .config import get_settings

_configured = False


def configure_logging() -> None:
    """Configure stdlib logging and structlog. Idempotent."""

    global _configured
    if _configured:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Route stdlib logging (uvicorn, sqlalchemy, etc.) through a basic handler.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger."""

    configure_logging()
    return structlog.get_logger(name)
