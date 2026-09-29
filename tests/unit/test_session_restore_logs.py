"""Restoring a session from its autosave writes logs only under the restored session id."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog

from dnd_simulator.logging_config import configure_logging
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    config = structlog.get_config()
    yield
    structlog.contextvars.clear_contextvars()
    structlog.reset_defaults()
    structlog.configure(**config)
    root.handlers[:] = handlers
    root.setLevel(level)


def _session_log_dirs(log_root: Path) -> set[str]:
    return {p.name for p in log_root.glob("session_*") if p.is_dir()}


def test_restore_from_autosave_creates_no_orphan_log_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Unset seed → start_game logs `world_seed_generated`, which is what used to land under a temporary id.
    monkeypatch.delenv("DND_WORLD_SEED", raising=False)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False, raising=False)
    log_root = tmp_path / "logs"
    configure_logging(log_level=logging.DEBUG, log_dir=log_root)

    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    sid = service.start_game().session_id
    service.autosave_session(sid)
    with service._sessions_lock:
        del service._sessions[sid]
    structlog.contextvars.clear_contextvars()
    before = _session_log_dirs(log_root)
    assert before == {f"session_{sid}"}

    restored = service.get_session(sid)

    assert restored.session_id == sid
    assert set(service._sessions) == {sid}
    assert _session_log_dirs(log_root) == before
    capsys.readouterr()
