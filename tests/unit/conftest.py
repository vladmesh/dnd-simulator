"""Global test configuration — English locale and quiet, test-scoped logging configuration."""

import logging
import os
from collections.abc import Iterator

import pytest
import structlog

# Must be set before any dnd_simulator module is imported, because i18n.py
# reads DND_LANGUAGE at import time.
os.environ["DND_LANGUAGE"] = "en"

from dnd_simulator.logging_config import configure_logging

# The production default (LOG_LEVEL=WARNING), so background session threads (autosave, eviction
# timers, round loops) do not print info records over the pytest report.
configure_logging(log_level=logging.WARNING)


@pytest.fixture(autouse=True)
def _restore_logging_config() -> Iterator[None]:
    """Undo a test's configure_logging (e.g. LOG_LEVEL=DEBUG via an app lifespan) after it ends.

    structlog and the stdlib root logger are process-global: without this, one DEBUG test leaves
    every later test, and the threads it outlives, logging JSON straight to the terminal.
    """
    saved = structlog.get_config()
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    structlog.configure(**saved)
    root.handlers[:] = handlers
    root.setLevel(level)
