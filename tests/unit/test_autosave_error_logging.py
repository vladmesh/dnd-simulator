from __future__ import annotations

from pathlib import Path

import structlog

from dnd_simulator.core.character import Ability
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _scores() -> dict[str, int]:
    return {
        Ability.STR.value: 15,
        Ability.DEX.value: 10,
        Ability.CON.value: 14,
        Ability.INT.value: 8,
        Ability.WIS.value: 12,
        Ability.CHA.value: 8,
    }


def test_create_player_logs_autosave_failure_and_still_returns_player(tmp_path: Path) -> None:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    session = service.start_game()

    def fail_autosave(session_id: str) -> None:
        raise RuntimeError(f"autosave failed for {session_id}")

    service.autosave_session = fail_autosave  # type: ignore[method-assign]

    with structlog.testing.capture_logs() as logs:
        player = service.create_player(
            session.session_id,
            {
                "name": "Tester",
                "race": "human",
                "class": "fighter",
                "ability_scores": _scores(),
            },
        )

    assert player.name == "Tester"
    failed = [entry for entry in logs if entry.get("event") == "create_player_autosave_failed"]
    assert len(failed) == 1
    assert failed[0]["session_id"] == session.session_id


def test_empty_session_evict_logs_autosave_failure_and_still_removes_session(tmp_path: Path) -> None:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    session = service.start_game()

    def fail_autosave(session_id: str) -> None:
        raise RuntimeError(f"autosave failed for {session_id}")

    service.autosave_session = fail_autosave  # type: ignore[method-assign]

    with structlog.testing.capture_logs() as logs:
        service._on_session_empty(session)

    assert session.session_id not in service._sessions
    failed = [entry for entry in logs if entry.get("event") == "session_empty_autosave_failed"]
    assert len(failed) == 1
    assert failed[0]["session_id"] == session.session_id
