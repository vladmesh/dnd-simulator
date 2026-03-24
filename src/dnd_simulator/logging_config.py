"""Structured logging configuration using structlog.

Modes:
    Default:     WARNING level, JSON to stderr.
    DEBUG=1:     DEBUG level, pretty console (TTY) or JSON (pipe/docker).
    LOG_DIR set: Additionally write denormalized JSONL files for navigation.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def configure_logging(
    *,
    debug: bool = False,
    log_dir: Path | None = None,
) -> None:
    """Configure structlog with contextvar-based context binding."""
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if debug and log_dir:
        from dnd_simulator.logging_file_dispatch import FileDispatchProcessor

        processors.append(FileDispatchProcessor(log_dir))

    if debug and sys.stderr.isatty():
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.WARNING,
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

    # Configure stdlib logging for third-party libraries (uvicorn, openai)
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
