"""Time-of-day encounter gating (Sprint 018 phase 4 task 1).

An encounter entry can carry a ``time_of_day`` tag: a night-tagged entry rolls
only when it is night at that location, a day-tagged entry only by day, an
untagged entry always (the pre-phase-4 behaviour). Day/night comes from the
geography layer via the ``IS_DAYLIGHT`` query, so these tests drive the real
activation path and just vary ``world.time`` to switch phase.

``random`` is mocked so the chance gate always clears and the count is fixed at
one; the only variable under test is the clock. The world is ``test_vale``:
- ``night_hollow`` (darkwood, latitude 45) has a night-only bandit table;
- ``crossroads`` carries an untagged regional goblin table.

At latitude 45 in month 6 daylight runs from about 04:18 to 19:42, so the default
start hour (10) is day and hour 2 is night.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from dnd_simulator.core.character import Creature
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.service.game_service import GameService
from dnd_simulator.service.session import GameSession
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
FIGHTER_SCORES = {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8}


def _session_with_player(tmp_path: Path, location: str) -> GameSession:
    svc = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=CONTENT_DIR)
    session = svc.start_game("test_vale")
    svc.create_player(
        session.session_id,
        {
            "name": "Scout",
            "race": "human",
            "class": "fighter",
            "alignment": "true_neutral",
            "ability_scores": FIGHTER_SCORES,
            "fighting_style": "defense",
            "start_location": location,
        },
    )
    return session


def _entities(session: GameSession) -> EntitiesLayer:
    layer = session.world.layers[4]
    assert isinstance(layer, EntitiesLayer)
    return layer


def _set_hour(session: GameSession, hour: int) -> None:
    """Force the world clock to a specific hour (month preserved for the daylight calc)."""
    session.world.time = replace(session.world.time, hour=hour)


def _activate(session: GameSession) -> None:
    """Run one activation pass with a guaranteed chance hit (count fixed at 1)."""
    ents = _entities(session)
    qfn = session.world.make_query_fn("entities")
    efn = session.world.make_emit_fn("entities")
    with patch("random.random", return_value=0.0), patch("random.randint", return_value=1):
        ents.update_activation(session.world.time, query_fn=qfn, emit_fn=efn)


def _monster_names_at(session: GameSession, location_id: str) -> list[str]:
    """Names of live encounter monster spawns at a location (excludes player and authored NPCs)."""
    ents = _entities(session)
    return sorted(
        e.name
        for e in ents._entities.values()
        if isinstance(e, Creature)
        and not isinstance(e, (PlayerCharacter, Npc))
        and e.location_id == location_id
        and e.is_alive
    )


class TestNightOnlyEncounter:
    def test_silent_by_day(self, tmp_path: Path) -> None:
        """The night-only hollow table does not roll during the day."""
        session = _session_with_player(tmp_path, "night_hollow")
        _set_hour(session, 10)  # day at latitude 45, month 6
        _activate(session)
        assert _monster_names_at(session, "night_hollow") == []

    def test_fires_at_night(self, tmp_path: Path) -> None:
        """The same table rolls once it is night."""
        session = _session_with_player(tmp_path, "night_hollow")
        _set_hour(session, 2)  # night
        _activate(session)
        assert "Bandit" in _monster_names_at(session, "night_hollow")


class TestUntaggedEncounterIgnoresTime:
    def test_untagged_table_fires_at_night(self, tmp_path: Path) -> None:
        """An untagged table (the regional goblins) still rolls at night — gating only drops mismatched tags."""
        session = _session_with_player(tmp_path, "crossroads_tavern")
        _set_hour(session, 2)  # night
        _activate(session)
        assert "Goblin" in _monster_names_at(session, "crossroads_tavern")
