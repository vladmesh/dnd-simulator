"""Tests for the entities layer."""

import pytest

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.models import Event, EventType, GameDateTime, Query, TimeDelta
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import WorldState
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import (
    Npc,
    hour_in_range,
    resolve_schedule,
)


def _make_npcs() -> list[Npc]:
    return [
        Npc(
            id="smith",
            name="Edgar the Smith",
            location_id="silverport",
            role="blacksmith",
            personality="Gruff but fair.",
            settlement_id="silverport_city",
            schedule=resolve_schedule("blacksmith", "silverport_city"),
        ),
        Npc(
            id="guard",
            name="Guard Rodrik",
            location_id="silverport",
            role="guard",
            personality="Disciplined.",
            settlement_id="silverport_city",
            schedule=resolve_schedule("guard", "silverport_city"),
        ),
        Npc(
            id="farmer",
            name="Old Bran",
            location_id="highfield",
            role="farmer",
            personality="Quiet.",
            settlement_id="highfield_town",
            schedule=resolve_schedule("farmer", "highfield_town"),
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
        wolf = Creature(id="wolf1", name="Dire Wolf", location_id="greenwood")
        layer.add_entity(wolf)
        assert layer.get_entity("wolf1") is wolf

    def test_remove_entity(self) -> None:
        layer = _make_layer()
        layer.remove_entity("smith")
        assert layer.get_entity("smith") is None

    def test_remove_nonexistent_is_noop(self) -> None:
        layer = _make_layer()
        layer.remove_entity("nonexistent")  # no error


class TestScheduleComputed:
    """Schedule is now computed, not stored as state."""

    def test_blacksmith_working_midday(self) -> None:
        smith = _make_npcs()[0]
        assert smith.scheduled_activity(12).value == "working"
        assert smith.scheduled_location(12) == "silverport_city_smithy"

    def test_blacksmith_sleeping_at_night(self) -> None:
        smith = _make_npcs()[0]
        assert smith.scheduled_activity(3).value == "sleeping"
        assert smith.scheduled_location(3) == "silverport_city_home"

    def test_blacksmith_idle_evening(self) -> None:
        smith = _make_npcs()[0]
        assert smith.scheduled_activity(20).value == "idle"
        assert smith.scheduled_location(20) == "silverport_city_tavern"

    def test_guard_working_daytime(self) -> None:
        guard = _make_npcs()[1]
        assert guard.scheduled_activity(14).value == "working"
        assert guard.scheduled_location(14) == "silverport_city_patrol"

    def test_guard_sleeping_at_night(self) -> None:
        guard = _make_npcs()[1]
        assert guard.scheduled_activity(23).value == "sleeping"

    def test_location_override(self) -> None:
        smith = _make_npcs()[0]
        smith.location_override = "tavern_special"
        assert smith.current_location(12) == "tavern_special"
        smith.location_override = None
        assert smith.current_location(12) == "silverport_city_smithy"


class TestEntitiesAtLocation:
    def test_entities_at_location(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="entities_at_location", params={"location_id": "silverport", "hour": 12}))
        # NPCs are at their scheduled locations, not at "silverport"
        # Only non-NPC entities at "silverport" would show
        assert len(result.value) == 0

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
        player = PlayerCharacter(id="player", name="Hero", location_id="silverport")
        layer = EntitiesLayer(entities=[*npcs, player])
        result = layer.query(Query(question="entities_at_location", params={"location_id": "silverport", "hour": 12}))
        names = {e["name"] for e in result.value}
        assert "Hero" in names
        # NPCs are at scheduled locations, not at "silverport" directly

    def test_creature_on_layer(self) -> None:
        wolf = Creature(id="wolf_alpha", name="Alpha Wolf", location_id="greenwood")
        layer = EntitiesLayer(entities=[wolf])
        entity = layer.get_entity("wolf_alpha")
        assert entity is not None
        assert entity.name == "Alpha Wolf"

    def test_tick_is_noop(self) -> None:
        """Tick does nothing — schedule is computed."""
        entity = Entity(id="rock", name="Magic Rock", location_id="cave")
        layer = EntitiesLayer(entities=[entity])
        layer.tick(TimeDelta(seconds=0), _world_state(hour=12))  # no error


class TestSaveLoad:
    def test_round_trip_preserves_location(self) -> None:
        layer = _make_layer()

        state = layer.get_state()
        new_layer = EntitiesLayer(entities=_make_npcs())
        new_layer.load_state(state)

        info = new_layer.query(Query(question="entity_info", params={"entity_id": "smith"}))
        assert info.value["location_id"] == "silverport"

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

    def test_location_override_persists(self) -> None:
        layer = _make_layer()
        smith = layer.get_entity("smith")
        assert isinstance(smith, Npc)
        smith.location_override = "custom_spot"

        state = layer.get_state()
        new_layer = EntitiesLayer(entities=_make_npcs())
        new_layer.load_state(state)

        restored = new_layer.get_entity("smith")
        assert isinstance(restored, Npc)
        assert restored.location_override == "custom_spot"
