"""Tests for reputation-aware awareness, serialization, and YAML loading."""

from __future__ import annotations

from typing import Any

from dnd_simulator.content_loader.creatures import parse_npc, parse_player
from dnd_simulator.core.character import Character
from dnd_simulator.core.models import Answer, FactionRelation, Query, QueryType
from dnd_simulator.layers.entities.layer import EntitiesLayer


def _query_fn_with_relation(relation: FactionRelation):
    """Build a query_fn that returns a fixed faction relation."""

    def query_fn(target: str, query: Query) -> Answer:
        if target == "politics" and query.question == QueryType.FACTION_RELATION:
            return Answer(value=relation)
        if target == "politics" and query.question == QueryType.FACTION_NAME:
            return Answer(value="Some Faction")
        return Answer(value=None)

    return query_fn


# ---------------------------------------------------------------------------
# Awareness hostility with personal reputation
# ---------------------------------------------------------------------------


class TestAwarenessReputationHostility:
    """check_faction_hostility uses effective_relation when both entities are Creatures."""

    def test_personal_rep_makes_neutral_factions_hostile(self) -> None:
        """Observer has rep 10 with target's faction; factions are NEUTRAL by default → hostile."""
        observer = Character(
            id="outcast",
            name="Outcast",
            location_id="road",
            faction_id="humans",
            reputation={"goblins": 10},
        )
        target = Character(
            id="goblin",
            name="Goblin",
            location_id="road",
            faction_id="goblins",
        )

        layer = EntitiesLayer([observer, target])
        query_fn = _query_fn_with_relation(FactionRelation.NEUTRAL)

        result = layer._awareness.check_faction_hostility(observer, target, query_fn)
        assert result is True

    def test_personal_rep_overrides_hostile_factions_to_friendly(self) -> None:
        """Factions are HOSTILE, but observer has rep 80 with target's faction → not hostile."""
        observer = Character(
            id="diplomat",
            name="Diplomat",
            location_id="road",
            faction_id="humans",
            reputation={"orcs": 80},
        )
        target = Character(
            id="orc",
            name="Orc",
            location_id="road",
            faction_id="orcs",
        )

        layer = EntitiesLayer([observer, target])
        query_fn = _query_fn_with_relation(FactionRelation.HOSTILE)

        result = layer._awareness.check_faction_hostility(observer, target, query_fn)
        assert result is False

    def test_exile_hostile_to_own_faction(self) -> None:
        """Observer has rep 10 with OWN faction → hostile to same-faction creature."""
        exile = Character(
            id="exile",
            name="Exile",
            location_id="road",
            faction_id="kingdom",
            reputation={"kingdom": 10},
        )
        loyalist = Character(
            id="guard",
            name="Guard",
            location_id="road",
            faction_id="kingdom",
        )

        layer = EntitiesLayer([exile, loyalist])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "politics" and query.question == QueryType.FACTION_NAME:
                return Answer(value="Kingdom")
            # Same faction — should NOT need faction relation query
            raise AssertionError("Should not query faction relation for exile scenario")

        result = layer._awareness.check_faction_hostility(exile, loyalist, query_fn)
        assert result is True

    def test_no_personal_rep_falls_back_to_faction_relation(self) -> None:
        """No personal reputation → uses faction-to-faction relation as before."""
        observer = Character(
            id="knight",
            name="Knight",
            location_id="road",
            faction_id="kingdom",
        )
        enemy = Character(
            id="orc",
            name="Orc",
            location_id="road",
            faction_id="horde",
        )

        layer = EntitiesLayer([observer, enemy])
        query_fn = _query_fn_with_relation(FactionRelation.HOSTILE)

        result = layer._awareness.check_faction_hostility(observer, enemy, query_fn)
        assert result is True


# ---------------------------------------------------------------------------
# Save/load roundtrip for reputation
# ---------------------------------------------------------------------------


class TestReputationSerialization:
    """Reputation dict survives get_state → load_state cycle."""

    def test_save_load_roundtrip_preserves_reputation(self) -> None:
        creature = Character(
            id="c1",
            name="Adventurer",
            location_id="town",
            faction_id="humans",
            reputation={"goblin": 30, "human": 90},
        )

        layer = EntitiesLayer([creature])
        state = layer.get_state()

        # Verify serialized data contains reputation
        entities_data: dict[str, Any] = state["entities"]  # type: ignore[assignment]
        assert entities_data["c1"]["reputation"] == {"goblin": 30, "human": 90}

        # Load into fresh layer with same creature (empty reputation)
        creature2 = Character(
            id="c1",
            name="Adventurer",
            location_id="town",
            faction_id="humans",
        )
        layer2 = EntitiesLayer([creature2])
        layer2.load_state(state)

        assert creature2.reputation == {"goblin": 30, "human": 90}

    def test_empty_reputation_serialized_as_empty_dict(self) -> None:
        creature = Character(
            id="c1",
            name="Plain",
            location_id="town",
        )

        layer = EntitiesLayer([creature])
        state = layer.get_state()

        entities_data: dict[str, Any] = state["entities"]  # type: ignore[assignment]
        assert entities_data["c1"]["reputation"] == {}


# ---------------------------------------------------------------------------
# YAML content loading
# ---------------------------------------------------------------------------


class TestReputationYamlLoading:
    """Reputation field parsed from YAML content definitions."""

    def test_npc_with_reputation_parsed(self) -> None:
        npc_data: dict[str, object] = {
            "name": {"en": "Outcast"},
            "faction": "goblins",
            "reputation": {"goblin": 20, "human": 60},
        }
        npc = parse_npc("outcast", npc_data)
        assert npc.reputation == {"goblin": 20, "human": 60}

    def test_npc_without_reputation_has_empty_dict(self) -> None:
        npc_data: dict[str, object] = {
            "name": {"en": "Regular"},
            "faction": "goblins",
        }
        npc = parse_npc("regular", npc_data)
        assert npc.reputation == {}

    def test_player_with_reputation_parsed(self) -> None:
        player_data: dict[str, object] = {
            "name": {"en": "Hero"},
            "faction": "humans",
            "reputation": {"orcs": 10},
        }
        player = parse_player(player_data)
        assert player.reputation == {"orcs": 10}
