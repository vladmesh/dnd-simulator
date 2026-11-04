"""Branch coverage for EntitiesLayer queries: filters, fallbacks and non-character entities."""

from __future__ import annotations

import pytest

from dnd_simulator.core.character import Character, Creature, NpcRole
from dnd_simulator.core.container import Container
from dnd_simulator.core.models import EntityKind, Query, QueryType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc


def _ask(layer: EntitiesLayer, question: QueryType, **params: object) -> object:
    return layer.query(Query(question=question, params=params)).value


def _world() -> EntitiesLayer:
    player = PlayerCharacter(id="hero", name="Hero", location_id="square")
    npc = Npc(id="smith", name="Edgar", location_id="square", role=NpcRole.BLACKSMITH, settlement_id="town")
    monster = Creature(id="wolf", name="Wolf", location_id="woods")
    sleeper = Character(id="sleeper", name="Sleeper", location_id="square")
    sleeper.active = False
    chest = Container(id="chest", name="Chest", location_id="square", gold=5)
    return EntitiesLayer([player, npc, monster, sleeper, chest])


class TestPlayerQuery:
    def test_without_id_returns_first_player(self) -> None:
        player = _ask(_world(), QueryType.PLAYER)
        assert isinstance(player, PlayerCharacter)
        assert player.id == "hero"

    def test_without_id_and_no_player_returns_none(self) -> None:
        layer = EntitiesLayer([Creature(id="wolf", name="Wolf", location_id="woods")])
        assert _ask(layer, QueryType.PLAYER) is None

    def test_id_of_non_player_returns_none(self) -> None:
        assert _ask(_world(), QueryType.PLAYER, id="smith") is None


class TestEntitiesAtLocation:
    def test_skips_dormant_and_summarizes_npc(self) -> None:
        result = _ask(_world(), QueryType.ENTITIES_AT_LOCATION, location_id="square", hour=12)
        assert isinstance(result, list)
        by_id = {row["id"]: row for row in result}
        assert "sleeper" not in by_id
        assert "chest" in by_id
        assert "is_wounded" not in by_id["chest"]
        smith = by_id["smith"]
        assert smith["role"] == NpcRole.BLACKSMITH.value
        assert smith["location_label"] == "square"
        assert "activity" in smith
        assert "activity_flavor" in smith


class TestAllCreaturesFilters:
    @staticmethod
    def _ids(**params: object) -> set[str]:
        result = _ask(_world(), QueryType.ALL_CREATURES, **params)
        assert isinstance(result, list)
        return {row["id"] for row in result}

    def test_no_filter_excludes_containers(self) -> None:
        assert self._ids() == {"hero", "smith", "wolf", "sleeper"}

    def test_active_filter(self) -> None:
        assert self._ids(active=False) == {"sleeper"}

    def test_location_filter(self) -> None:
        assert self._ids(location_id="woods") == {"wolf"}

    @pytest.mark.parametrize(
        ("kind", "expected"),
        [
            (EntityKind.PLAYER, {"hero"}),
            (EntityKind.NPC, {"smith"}),
            (EntityKind.MONSTER, {"wolf", "sleeper"}),
        ],
    )
    def test_kind_filter(self, kind: EntityKind, expected: set[str]) -> None:
        assert self._ids(entity_type=kind.value) == expected


class TestNonCharacterFallbacks:
    def test_npc_info_for_non_npc_raises(self) -> None:
        with pytest.raises(ValueError, match="NPC 'wolf' not found"):
            _ask(_world(), QueryType.NPC_INFO, npc_id="wolf")

    @pytest.mark.parametrize(
        "question",
        [QueryType.PERCEIVED_LOG, QueryType.NEW_PERCEIVED_EVENTS, QueryType.NEW_RAW_EVENTS],
    )
    def test_event_logs_of_non_character_are_empty(self, question: QueryType) -> None:
        assert _ask(_world(), question, entity_id="wolf") == []

    def test_perceive_entity_unknown_target_falls_back_to_id(self) -> None:
        assert _ask(_world(), QueryType.PERCEIVE_ENTITY, observer_id="hero", target_id="ghost") == "ghost"

    def test_combat_info_without_combat_is_none(self) -> None:
        assert _ask(_world(), QueryType.COMBAT_INFO, location_id="square") is None

    def test_unknown_query_raises(self) -> None:
        layer = _world()
        with pytest.raises(ValueError, match="Unknown entities query"):
            layer.query(Query(question=QueryType.IS_DAYLIGHT, params={}))


class TestCharacterHappyPaths:
    def test_all_npcs_lists_only_active_npcs(self) -> None:
        result = _ask(_world(), QueryType.ALL_NPCS)
        assert isinstance(result, list)
        assert [row["id"] for row in result] == ["smith"]

    def test_new_raw_events_of_character_start_empty(self) -> None:
        assert _ask(_world(), QueryType.NEW_RAW_EVENTS, entity_id="hero") == []

    def test_perceive_entity_uses_observer_perception(self) -> None:
        layer = _world()
        expected = layer.get_entity("hero").perceive(layer.get_entity("smith"))  # type: ignore[union-attr]
        assert _ask(layer, QueryType.PERCEIVE_ENTITY, observer_id="hero", target_id="smith") == expected
