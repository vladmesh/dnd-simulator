"""Structured logging configuration using structlog.

LOG_LEVEL env var controls verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL).
LOG_DIR env var enables file dispatch (JSONL per domain).
When LOG_LEVEL <= DEBUG and stderr is a TTY, use pretty console renderer.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def configure_logging(
    *,
    log_level: int = logging.WARNING,
    log_dir: Path | None = None,
) -> None:
    """Configure structlog with contextvar-based context binding."""
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_level <= logging.DEBUG and log_dir:
        from dnd_simulator.logging_file_dispatch import FileDispatchProcessor

        processors.append(FileDispatchProcessor(log_dir))

    if log_level <= logging.DEBUG and sys.stderr.isatty():
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

    # Configure stdlib logging for third-party libraries (uvicorn, openai)
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
