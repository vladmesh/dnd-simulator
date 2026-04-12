"""Tests for SaveCommands.autosave_all_sessions — failure of one session must not silence others."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import structlog

from dnd_simulator.service.commands_save import SaveCommands


class _Svc(SaveCommands):
    """Minimal SaveCommands harness — overrides autosave_session per-test."""

    def __init__(self, sessions: dict[str, Any]) -> None:
        self._sessions = sessions  # type: ignore[assignment]
        self._store = MagicMock()
        self.saved: list[str] = []

    def autosave_session(self, session_id: str) -> None:  # type: ignore[override]
        raise NotImplementedError


class TestAutosaveAllSessions:
    def test_one_failure_does_not_block_others_and_logs(self) -> None:
        svc = _Svc({"a": object(), "b": object(), "c": object()})

        def autosave(sid: str) -> None:
            if sid == "b":
                raise RuntimeError("disk full")
            svc.saved.append(sid)

        svc.autosave_session = autosave  # type: ignore[method-assign]

        with structlog.testing.capture_logs() as logs:
            svc.autosave_all_sessions()

        assert svc.saved == ["a", "c"]
        failed = [e for e in logs if e.get("event") == "autosave_failed"]
        assert len(failed) == 1
        assert failed[0]["session_id"] == "b"
