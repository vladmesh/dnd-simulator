from __future__ import annotations

import random
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from dnd_simulator.core.world import World
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.service.commands_save import SaveCommands
from dnd_simulator.service.session import GameSession
from dnd_simulator.storage.store import JsonFileStore


class _Svc(SaveCommands):
    def __init__(self, session: GameSession, store: JsonFileStore) -> None:
        self._sessions = {session.session_id: session}
        self._sessions_lock = threading.RLock()
        self._store = store


@pytest.mark.parametrize("replaced", [False, True], ids=["removed", "replaced-same-id"])
def test_stale_session_autosave_preserves_existing_save(tmp_path: Path, replaced: bool) -> None:
    dice_rng = random.Random(42)
    world = World(
        layers=[
            GeographyLayer(weather_seed=42),
            PoliticsLayer(seed=42),
            SettlementsLayer(),
            EcologyLayer(seed=42),
            EntitiesLayer(seed=42, dice_rng=dice_rng),
        ],
        seed=42,
    )
    session = GameSession(session_id="a", world=world, world_name="world", dice_rng=dice_rng)
    store = JsonFileStore(tmp_path)
    svc = _Svc(session, store)

    assert svc._autosave_active_session(session) is True
    saved = store.load("session_a", world="world")
    assert saved["meta"]["lang"] == "en"

    with svc._sessions_lock:
        if replaced:
            svc._sessions[session.session_id] = replace(session)
        else:
            del svc._sessions[session.session_id]
    session.lang = "fr"

    assert svc._autosave_active_session(session) is False
    assert store.list_saves(world="world") == ["session_a"]
    assert store.load("session_a", world="world") == saved
