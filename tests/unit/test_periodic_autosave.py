from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import structlog

from dnd_simulator.adapters.api import app as app_module
from dnd_simulator.adapters.api.app import _autosave_interval_from_env, _periodic_autosave, lifespan
from dnd_simulator.core.character import Ability
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


class _FakeService:
    def __init__(self) -> None:
        self.calls = 0
        self.failures_remaining = 0

    def autosave_all_sessions(self) -> None:
        self.calls += 1
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise RuntimeError("disk offline")


async def _cancel(task: asyncio.Task[None]) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.fixture
def default_scores() -> dict[str, int]:
    return {
        Ability.STR.value: 15,
        Ability.DEX.value: 10,
        Ability.CON.value: 14,
        Ability.INT.value: 8,
        Ability.WIS.value: 12,
        Ability.CHA.value: 8,
    }


def test_autosave_interval_comes_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DND_AUTOSAVE_SECONDS", "0.25")
    assert _autosave_interval_from_env() == 0.25


def test_autosave_interval_defaults_to_120_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DND_AUTOSAVE_SECONDS", raising=False)
    assert _autosave_interval_from_env() == 120.0


@pytest.mark.parametrize("raw", ["abc", "0", "-1"])
def test_invalid_autosave_interval_fails_fast(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("DND_AUTOSAVE_SECONDS", raw)
    with pytest.raises(ValueError):
        _autosave_interval_from_env()


async def test_periodic_autosave_persists_fresh_session_state(
    tmp_path: Path,
    default_scores: dict[str, int],
) -> None:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    session = service.start_game()
    player = service.create_player(
        session.session_id,
        {
            "name": "Tester",
            "race": "human",
            "class": "fighter",
            "ability_scores": default_scores,
        },
    )
    player.location_id = "blacksmith"

    task = asyncio.create_task(_periodic_autosave(service, 0.01))
    try:
        await asyncio.sleep(0.08)
    finally:
        await _cancel(task)

    saved = service._store.load(f"session_{session.session_id}", world=session.world_name)
    assert saved["schema_version"] == 1
    entities = saved["world"]["layers"]["entities"]["entities"]
    saved_player = entities[player.id]
    assert saved_player["location_id"] == "blacksmith"


async def test_periodic_autosave_logs_error_and_keeps_ticking() -> None:
    service = _FakeService()
    service.failures_remaining = 1

    with structlog.testing.capture_logs() as logs:
        task = asyncio.create_task(_periodic_autosave(service, 0.01))
        try:
            await asyncio.sleep(0.08)
        finally:
            await _cancel(task)

    assert service.calls >= 2
    assert any(entry.get("event") == "periodic_autosave_failed" for entry in logs)


async def test_lifespan_cancels_periodic_task_before_final_autosave(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class Service(_FakeService):
        def autosave_all_sessions(self) -> None:
            events.append("save")

    class Store:
        def __init__(self, path: Path) -> None:
            self.path = path

    async def fake_periodic(service: Service, interval: float) -> None:
        events.append("periodic_started")
        try:
            await asyncio.Event().wait()
        finally:
            events.append("periodic_cancelled")

    monkeypatch.setattr(app_module, "JsonFileStore", Store)
    monkeypatch.setattr(app_module, "GameService", lambda **_: Service())
    monkeypatch.setattr(app_module, "set_service", lambda service: None)
    monkeypatch.setattr(app_module, "_autosave_interval_from_env", lambda: 0.01)
    monkeypatch.setattr(app_module, "_periodic_autosave", fake_periodic)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DND_DICE_SEED", raising=False)

    async with lifespan(MagicMock()):
        await asyncio.sleep(0)
        assert events == ["periodic_started"]

    assert events == ["periodic_started", "periodic_cancelled", "save"]
