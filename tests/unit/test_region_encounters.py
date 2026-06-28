"""Region encounter-table fallthrough tests (Sprint 018 phase 3 task 2).

Encounter tables can be declared per region. A location with no table of its own
falls through to its region's table; a location with its own table overrides the
region default (no merge). The resolution happens at load time in ``GameService``
(mirroring how battle-map region defaults collapse to per-location configs), so
the runtime activation path is unchanged — these tests drive that real path and
observe the spawn in the world rather than poking internals.

``random`` is mocked so the roll is deterministic: ``random.random() -> 0.0``
always clears the chance gate and ``random.randint -> 1`` fixes the count at one.

The world is ``test_vale``:
- region ``crossroads`` carries a regional goblin table;
- ``forest_road`` (in crossroads) keeps its own bandit table → override;
- ``forest_edge`` (in darkwood, no regional table, no lair) → no encounters.
"""

from __future__ import annotations

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


def _activate(session: GameSession) -> None:
    """Run one activation pass with a guaranteed encounter hit (count fixed at 1)."""
    ents = _entities(session)
    qfn = session.world.make_query_fn("entities")
    efn = session.world.make_emit_fn("entities")
    with patch("random.random", return_value=0.0), patch("random.randint", return_value=1):
        ents.update_activation(session.world.time, query_fn=qfn, emit_fn=efn)


def _monster_names_at(session: GameSession, location_id: str) -> list[str]:
    """Names of live encounter/lair monster spawns at a location (excludes player and authored NPCs)."""
    ents = _entities(session)
    return sorted(
        e.name
        for e in ents._entities.values()
        if isinstance(e, Creature)
        and not isinstance(e, (PlayerCharacter, Npc))
        and e.location_id == location_id
        and e.is_alive
    )


class TestRegionEncounterFallthrough:
    def test_tableless_location_rolls_region_table(self, tmp_path: Path) -> None:
        """A crossroads location with no table of its own rolls the regional goblin table."""
        session = _session_with_player(tmp_path, "crossroads_tavern")
        _activate(session)
        assert "Goblin" in _monster_names_at(session, "crossroads_tavern")

    def test_location_outside_any_table_stays_empty(self, tmp_path: Path) -> None:
        """A darkwood location with no regional table (and no lair) spawns nothing."""
        session = _session_with_player(tmp_path, "forest_edge")
        _activate(session)
        assert _monster_names_at(session, "forest_edge") == []


class TestRegionEncounterOverride:
    def test_own_table_overrides_region(self, tmp_path: Path) -> None:
        """forest_road has its own bandit table → it rolls bandits, never the regional goblins."""
        session = _session_with_player(tmp_path, "forest_road")
        _activate(session)
        names = _monster_names_at(session, "forest_road")
        assert "Bandit" in names
        assert "Goblin" not in names


class TestRegionEncounterCooldownPerLocation:
    def test_two_tableless_locations_roll_independently(self, tmp_path: Path) -> None:
        """Cooldown is keyed by location, so two tableless crossroads locations each roll the region table."""
        session = _session_with_player(tmp_path, "crossroads_tavern")
        _activate(session)
        assert "Goblin" in _monster_names_at(session, "crossroads_tavern")

        player = session.get_player()
        assert player is not None
        player.location_id = "crossroads_market"
        _activate(session)
        assert "Goblin" in _monster_names_at(session, "crossroads_market")
