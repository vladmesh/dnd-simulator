"""Tests for SaveCommands.autosave_all_sessions — failure of one session must not silence others."""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock

import structlog

from dnd_simulator.service.commands_save import SaveCommands


class _Svc(SaveCommands):
    """Minimal SaveCommands harness — overrides autosave_session per-test."""

    def __init__(self, sessions: dict[str, Any]) -> None:
        self._sessions = sessions  # type: ignore[assignment]
        self._sessions_lock = threading.RLock()
        self._store = MagicMock()
        self.saved: list[str] = []


class TestAutosaveAllSessions:
    def test_one_failure_does_not_block_others_and_logs(self) -> None:
        sessions = {sid: MagicMock() for sid in ("a", "b", "c")}
        for sid, session in sessions.items():
            session.session_id = sid
            session.build_save_game.return_value.model_dump.return_value = {}
            session.world_name = "world"
        svc = _Svc(sessions)

        def autosave(name: str, data: dict[str, Any], *, world: str = "") -> None:
            sid = name.removeprefix("session_")
            if sid == "b":
                raise RuntimeError("disk full")
            svc.saved.append(sid)

        svc._store.save.side_effect = autosave

        with structlog.testing.capture_logs() as logs:
            svc.autosave_all_sessions()

        assert svc.saved == ["a", "c"]
        failed = [e for e in logs if e.get("event") == "autosave_failed"]
        assert len(failed) == 1
        assert failed[0]["session_id"] == "b"
