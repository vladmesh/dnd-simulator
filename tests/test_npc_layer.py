"""Tests for the NPC layer."""

import pytest

from dnd_simulator.core.models import Event, EventType, GameDateTime, Query, TimeDelta
from dnd_simulator.core.world import WorldState
from dnd_simulator.layers.npcs.layer import NpcLayer
from dnd_simulator.layers.npcs.models import (
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


def _make_layer() -> NpcLayer:
    return NpcLayer(npcs=_make_npcs())


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
        assert layer.name == "npcs"

    def test_handle_event_returns_empty(self) -> None:
        layer = _make_layer()
        event = Event(event_type=EventType.WEATHER_CHANGED, source_layer="geography")
        assert layer.handle_event(event) == []


class TestSchedule:
    def test_blacksmith_working_midday(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=12))
        info = layer.query(Query(question="npc_info", params={"npc_id": "smith"}))
        assert info.value["activity"] == "working"
        assert info.value["location_label"] == "smithy"

    def test_blacksmith_sleeping_at_night(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=3))
        info = layer.query(Query(question="npc_info", params={"npc_id": "smith"}))
        assert info.value["activity"] == "sleeping"
        assert info.value["location_label"] == "home"

    def test_blacksmith_idle_evening(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=20))
        info = layer.query(Query(question="npc_info", params={"npc_id": "smith"}))
        assert info.value["activity"] == "idle"
        assert info.value["location_label"] == "tavern"

    def test_guard_working_daytime(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=14))
        info = layer.query(Query(question="npc_info", params={"npc_id": "guard"}))
        assert info.value["activity"] == "working"
        assert info.value["location_label"] == "patrol"

    def test_guard_sleeping_at_night(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=23))
        info = layer.query(Query(question="npc_info", params={"npc_id": "guard"}))
        assert info.value["activity"] == "sleeping"


class TestQueries:
    def test_npcs_in_region(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=12))
        result = layer.query(Query(question="npcs_in_region", params={"region_id": "silverport"}))
        assert len(result.value) == 2
        names = {n["name"] for n in result.value}
        assert names == {"Edgar the Smith", "Guard Rodrik"}

    def test_npcs_in_other_region(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="npcs_in_region", params={"region_id": "highfield"}))
        assert len(result.value) == 1
        assert result.value[0]["name"] == "Old Bran"

    def test_npcs_empty_region(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="npcs_in_region", params={"region_id": "greenwood"}))
        assert result.value == []

    def test_npc_info(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="npc_info", params={"npc_id": "smith"}))
        assert result.value["name"] == "Edgar the Smith"
        assert result.value["role"] == "blacksmith"
        assert result.value["personality"] == "Gruff but fair."

    def test_unknown_query(self) -> None:
        layer = _make_layer()
        with pytest.raises(ValueError, match="Unknown npcs query"):
            layer.query(Query(question="nonsense", params={}))


class TestSaveLoad:
    def test_round_trip_preserves_activity(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta(seconds=0), _world_state(hour=12))

        state = layer.get_state()
        new_layer = NpcLayer(npcs=_make_npcs())
        new_layer.load_state(state)

        info = new_layer.query(Query(question="npc_info", params={"npc_id": "smith"}))
        assert info.value["activity"] == "working"
        assert info.value["location_label"] == "smithy"

    def test_conversation_summary_persists(self) -> None:
        layer = _make_layer()
        # Simulate storing a conversation summary
        npc = layer._npcs["smith"]
        npc.conversation_summary = "Player asked about iron supply."

        state = layer.get_state()
        new_layer = NpcLayer(npcs=_make_npcs())
        new_layer.load_state(state)

        info = new_layer.query(Query(question="npc_info", params={"npc_id": "smith"}))
        assert info.value["conversation_summary"] == "Player asked about iron supply."
