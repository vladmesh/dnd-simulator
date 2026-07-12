from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
import structlog

from dnd_simulator.core.character import Ability
from dnd_simulator.service import GameService
from dnd_simulator.service.errors import SessionNotFoundError
from dnd_simulator.storage.store import JsonFileStore, SaveStore


class _BlockingStore(SaveStore):
    def __init__(self) -> None:
        self.save_started = threading.Event()
        self.release_save = threading.Event()
        self.save_calls = 0
        self.data: dict[tuple[str, str], dict[str, Any]] = {}

    def save(self, name: str, data: dict[str, Any], *, world: str = "") -> None:
        self.save_calls += 1
        self.save_started.set()
        assert self.release_save.wait(timeout=2)
        self.data[(world, name)] = data

    def load(self, name: str, *, world: str = "") -> dict[str, Any]:
        try:
            return self.data[(world, name)]
        except KeyError:
            for (_saved_world, saved_name), data in self.data.items():
                if saved_name == name:
                    return data
            raise KeyError(name) from None

    def list_saves(self, *, world: str = "") -> list[str]:
        return [name for saved_world, name in self.data if saved_world == world]

    def delete(self, name: str, *, world: str = "") -> None:
        try:
            del self.data[(world, name)]
        except KeyError:
            raise KeyError(name) from None


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

    def fail_save(name: str, data: dict[str, Any], *, world: str = "") -> None:
        raise RuntimeError(f"autosave failed for {name}")

    service._store.save = fail_save  # type: ignore[method-assign]

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

    def fail_save(name: str, data: dict[str, Any], *, world: str = "") -> None:
        raise RuntimeError(f"autosave failed for {name}")

    service._store.save = fail_save  # type: ignore[method-assign]

    with structlog.testing.capture_logs() as logs:
        service._on_session_empty(session)

    assert session.session_id not in service._sessions
    failed = [entry for entry in logs if entry.get("event") == "session_empty_autosave_failed"]
    assert len(failed) == 1
    assert failed[0]["session_id"] == session.session_id


def test_empty_session_evict_after_delete_is_noop(tmp_path: Path) -> None:
    """Evict timer firing after an explicit DELETE must not autosave, resurrect, or log an error."""
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    session = service.start_game()
    service.autosave_session(session.session_id)  # autosave exists on disk — resurrect bait
    service.delete_session(session.session_id)

    with structlog.testing.capture_logs() as logs:
        service._on_session_empty(session)

    assert session.session_id not in service._sessions
    assert not [e for e in logs if e.get("event") == "session_empty_autosave_failed"]
    assert [e for e in logs if e.get("event") == "session_empty_evict_skipped"]


def test_concurrent_evict_runs_one_autosave() -> None:
    store = _BlockingStore()
    service = GameService(store=store)
    session = service.start_game()
    first = threading.Thread(target=service._on_session_empty, args=(session,))
    second = threading.Thread(target=service._on_session_empty, args=(session,))

    first.start()
    assert store.save_started.wait(timeout=2)
    second.start()
    store.release_save.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert store.save_calls == 1
    assert session.session_id not in service._sessions


def test_explicit_delete_racing_evict_does_not_leave_restorable_autosave() -> None:
    store = _BlockingStore()
    service = GameService(store=store)
    session = service.start_game()
    evict = threading.Thread(target=service._on_session_empty, args=(session,))
    evict.start()
    assert store.save_started.wait(timeout=2)

    delete = threading.Thread(target=service.delete_session, args=(session.session_id,))
    delete.start()
    store.release_save.set()
    evict.join(timeout=2)
    delete.join(timeout=2)

    assert not evict.is_alive()
    assert not delete.is_alive()
    with pytest.raises(SessionNotFoundError):
        service.get_session(session.session_id)
