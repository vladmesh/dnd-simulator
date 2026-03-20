"""Tests for the entities layer."""

import pytest

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.models import Event, EventType, GameDateTime, Query, TimeDelta
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import WorldState
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import (
    DEFAULT_SCHEDULES,
    Npc,
    hour_in_range,
)


def _make_npcs() -> list[Npc]:
    return [
        Npc(
            id="smith",
            name="Edgar the Smith",
            region_id="silverport",
            role="blacksmith",
            personality="Gruff but fair.",
            settlement_id="silverport_city",
            schedule=list(DEFAULT_SCHEDULES["blacksmith"]),
        ),
        Npc(
            id="guard",
            name="Guard Rodrik",
            region_id="silverport",
            role="guard",
            personality="Disciplined.",
            settlement_id="silverport_city",
            schedule=list(DEFAULT_SCHEDULES["guard"]),
        ),
        Npc(
            id="farmer",
            name="Old Bran",
            region_id="highfield",
            role="farmer",
            personality="Quiet.",
            settlement_id="highfield_town",
            schedule=list(DEFAULT_SCHEDULES["farmer"]),
        ),
    ]


def _make_layer() -> EntitiesLayer:
    return EntitiesLayer(entities=_make_npcs())


def _world_state(hour: int = 12) -> WorldState:
    return WorldState(
        time=GameDateTime(year=1490, month=6, day=1, hour=hour),
        layer_states={},
    )


class TestHourInRange:
    def test_normal_range(self) -> None:
        assert hour_in_range(12, 8, 20) is True
        assert hour_in_range(7, 8, 20) is False
        assert hour_in_range(20, 8, 20) is False

    def test_midnight_wrap(self) -> None:
        assert hour_in_range(23, 22, 6) is True
        assert hour_in_range(0, 22, 6) is True
        assert hour_in_range(5, 22, 6) is True
        assert hour_in_range(6, 22, 6) is False
        assert hour_in_range(12, 22, 6) is False


class TestLayerBasics:
    def test_name(self) -> None:
        layer = _make_layer()
        assert layer.name == "entities"

    def test_handle_event_returns_empty(self) -> None:
        layer = _make_layer()
        event = Event(event_type=EventType.WEATHER_CHANGED, source_layer="geography")
        result = layer.handle_event(event)
        assert result.success
        assert result.events == []


class TestGetEntity:
    def test_get_existing(self) -> None:
        layer = _make_layer()
        entity = layer.get_entity("smith")
        assert entity is not None
        assert entity.name == "Edgar the Smith"

    def test_get_missing(self) -> None:
        layer = _make_layer()
        assert layer.get_entity("nonexistent") is None

    def test_returns_direct_reference(self) -> None:
        layer = _make_layer()
        entity = layer.get_entity("smith")
        assert entity is not None
        entity.name = "Modified"
        assert layer.get_entity("smith") is not None
        assert layer.get_entity("smith").name == "Modified"


class TestAddRemove:
    def test_add_entity(self) -> None:
        layer = EntitiesLayer()
        wolf = Creature(id="wolf1", name="Dire Wolf", region_id="greenwood")
        layer.add_entity(wolf)
        assert layer.get_entity("wolf1") is wolf

    def test_remove_entity(self) -> None:
        layer = _make_layer()
        layer.remove_entity("smith")
        assert layer.get_entity("smith") is None

    def test_remove_nonexistent_is_noop(self) -> None:
        layer = _make_layer()
        layer.remove_entity("nonexistent")  # no error


class TestActivation:
    def test_inactive_entities_not_ticked(self) -> None:
        layer = _make_layer()
        smith = layer.get_entity("smith")
        assert isinstance(smith, Npc)
        smith.active = False
        layer.tick(TimeDelta(seconds=0), _world_state(hour=12))
        # Smith was not ticked, so activity stays at default IDLE
        assert smith.activity.value == "idle"

    def test_active_entities_ticked(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=12))
        smith = layer.get_entity("smith")
        assert isinstance(smith, Npc)
        assert smith.activity.value == "working"


class TestSchedule:
    def test_blacksmith_working_midday(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=12))
        info = layer.query(Query(question="entity_info", params={"entity_id": "smith"}))
        assert info.value["activity"] == "working"
        assert info.value["location_label"] == "smithy"

    def test_blacksmith_sleeping_at_night(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=3))
        info = layer.query(Query(question="entity_info", params={"entity_id": "smith"}))
        assert info.value["activity"] == "sleeping"
        assert info.value["location_label"] == "home"

    def test_blacksmith_idle_evening(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=20))
        info = layer.query(Query(question="entity_info", params={"entity_id": "smith"}))
        assert info.value["activity"] == "idle"
        assert info.value["location_label"] == "tavern"

    def test_guard_working_daytime(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=14))
        info = layer.query(Query(question="entity_info", params={"entity_id": "guard"}))
        assert info.value["activity"] == "working"
        assert info.value["location_label"] == "patrol"

    def test_guard_sleeping_at_night(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=23))
        info = layer.query(Query(question="entity_info", params={"entity_id": "guard"}))
        assert info.value["activity"] == "sleeping"


class TestQueries:
    def test_entities_in_region(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=12))
        result = layer.query(Query(question="entities_in_region", params={"region_id": "silverport"}))
        assert len(result.value) == 2
        names = {n["name"] for n in result.value}
        assert names == {"Edgar the Smith", "Guard Rodrik"}

    def test_entities_in_other_region(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="entities_in_region", params={"region_id": "highfield"}))
        assert len(result.value) == 1
        assert result.value[0]["name"] == "Old Bran"

    def test_entities_empty_region(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="entities_in_region", params={"region_id": "greenwood"}))
        assert result.value == []

    def test_entity_info(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="entity_info", params={"entity_id": "smith"}))
        assert result.value["name"] == "Edgar the Smith"
        assert result.value["role"] == "blacksmith"
        assert result.value["personality"] == "Gruff but fair."

    def test_unknown_query(self) -> None:
        layer = _make_layer()
        with pytest.raises(ValueError, match="Unknown entities query"):
            layer.query(Query(question="nonsense", params={}))


class TestMixedEntities:
    def test_player_and_npcs_coexist(self) -> None:
        npcs = _make_npcs()
        player = PlayerCharacter(id="player", name="Hero", region_id="silverport")
        layer = EntitiesLayer(entities=[*npcs, player])
        result = layer.query(Query(question="entities_in_region", params={"region_id": "silverport"}))
        names = {e["name"] for e in result.value}
        assert "Hero" in names
        assert "Edgar the Smith" in names

    def test_creature_on_layer(self) -> None:
        wolf = Creature(id="wolf_alpha", name="Alpha Wolf", region_id="greenwood")
        layer = EntitiesLayer(entities=[wolf])
        entity = layer.get_entity("wolf_alpha")
        assert entity is not None
        assert entity.name == "Alpha Wolf"

    def test_entity_on_tick_default_noop(self) -> None:
        """Base Entity.on_tick does nothing and doesn't crash."""
        entity = Entity(id="rock", name="Magic Rock", region_id="cave")
        layer = EntitiesLayer(entities=[entity])
        layer.tick(TimeDelta(seconds=0), _world_state(hour=12))  # no error


class TestSaveLoad:
    def test_round_trip_preserves_activity(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=12))

        state = layer.get_state()
        new_layer = EntitiesLayer(entities=_make_npcs())
        new_layer.load_state(state)

        info = new_layer.query(Query(question="entity_info", params={"entity_id": "smith"}))
        assert info.value["activity"] == "working"
        assert info.value["location_label"] == "smithy"

    def test_conversation_summary_persists(self) -> None:
        layer = _make_layer()
        smith = layer.get_entity("smith")
        assert isinstance(smith, Npc)
        smith.conversation_summary = "Player asked about iron supply."

        state = layer.get_state()
        new_layer = EntitiesLayer(entities=_make_npcs())
        new_layer.load_state(state)

        info = new_layer.query(Query(question="entity_info", params={"entity_id": "smith"}))
        assert info.value["conversation_summary"] == "Player asked about iron supply."

    def test_activation_persists(self) -> None:
        layer = _make_layer()
        smith = layer.get_entity("smith")
        assert smith is not None
        smith.active = False

        state = layer.get_state()
        new_layer = EntitiesLayer(entities=_make_npcs())
        new_layer.load_state(state)

        restored = new_layer.get_entity("smith")
        assert restored is not None
        assert restored.active is False
