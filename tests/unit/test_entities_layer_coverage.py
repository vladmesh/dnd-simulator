"""Coverage for entity-layer scheduling, event routing, and save validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dnd_simulator.core.character import Character, Entity
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.events import EntityFleePayload, EntityMovePayload
from dnd_simulator.core.intent import IntentType, TimedIntent, TravelIntent
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query
from dnd_simulator.layers.entities.layer import EntitiesLayer


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: Event) -> ActionResult:
    return ActionResult()


def test_nearest_wake_time_without_pending_intents() -> None:
    layer = EntitiesLayer(seed=0)
    assert layer.get_nearest_wake_time() is None

    layer.add_entity(Entity(id="chest", name="Chest", location_id="road"))
    layer.add_entity(Character(id="idle", name="Idle guard", location_id="road"))

    assert layer.get_nearest_wake_time() is None


@pytest.mark.parametrize(("wake_at", "arrival_at", "expected"), [(120, 90, 90), (90, 120, 90)])
def test_nearest_wake_time_compares_timed_and_travel_intents(wake_at: int, arrival_at: int, expected: int) -> None:
    waiter = Character(
        id="waiter",
        name="Waiting guard",
        location_id="road",
        current_intent=TimedIntent(kind=IntentType.WAIT, started_at_seconds=0, wake_at_seconds=wake_at),
    )
    traveler = Character(
        id="traveler",
        name="Traveler",
        location_id="road",
        current_intent=TravelIntent(
            started_at_seconds=0,
            destination_id="inn",
            remaining_route=("inn",),
            next_arrival_seconds=arrival_at,
        ),
    )
    chest = Entity(id="chest", name="Chest", location_id="road")
    layer = EntitiesLayer([chest, waiter, traveler], seed=0)

    assert layer.get_nearest_wake_time() == expected

    layer.remove_entity(traveler.id)
    assert layer.get_nearest_wake_time() == wake_at

    waiter.current_intent = None
    assert layer.get_nearest_wake_time() is None


def test_compass_move_updates_battle_map_and_logs_resolved_movement() -> None:
    mover = Character(id="mover", name="Guard", location_id="arena", in_combat=True)
    layer = EntitiesLayer([mover], seed=0)
    battle_map = BattleMap(width=40, height=40, positions={mover.id: Position(10, 10)})
    combat = CombatState(location_id="arena", turn_order=[mover.id], battle_map=battle_map)
    layer._combat._combats["arena"] = combat
    event = Event(
        event_type=EventType.ENTITY_MOVE,
        source_layer="entities",
        data=EntityMovePayload(entity_id=mover.id, direction="east", ft=10),
    )

    result = layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

    assert result.success
    assert layer.get_combat("arena") is combat
    assert battle_map.get_position(mover.id) == Position(20, 10)
    logged = layer.get_new_raw_events(mover)
    assert len(logged) == 1
    assert logged[0].event_type == EventType.ENTITY_MOVE
    assert logged[0].payload == EntityMovePayload(
        entity_id=mover.id,
        location_id="arena",
        from_x=10,
        from_y=10,
        to_x=20,
        to_y=10,
        distance_ft=10,
    )
    assert layer.get_new_perceived_events(mover) == ["You move to the east (10 ft)"]


def test_already_resolved_move_is_logged_once_without_moving_again() -> None:
    mover = Character(id="mover", name="Guard", location_id="arena", combat_position=(20, 10))
    layer = EntitiesLayer([mover], seed=0)
    event = Event(
        event_type=EventType.ENTITY_MOVE,
        source_layer="entities",
        data=EntityMovePayload(
            entity_id=mover.id,
            location_id="arena",
            from_x=10,
            from_y=10,
            to_x=20,
            to_y=10,
            distance_ft=10,
        ),
    )

    result = layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

    assert result.success
    assert result.events == []
    assert mover.combat_position == (20, 10)
    assert mover.location_id == "arena"
    assert layer.get_combat("arena") is None
    assert layer.get_new_raw_events(mover) == [event]
    assert layer.get_new_perceived_events(mover) == ["You move to the east (10 ft)"]
    assert layer.get_new_raw_events(mover) == []
    assert layer.get_new_perceived_events(mover) == []


@pytest.mark.parametrize("entity_id", ["missing", "chest"])
def test_flee_rejects_missing_or_noncreature_entity(entity_id: str) -> None:
    chest = Entity(id="chest", name="Chest", location_id="arena")
    observer = Character(id="observer", name="Guard", location_id="arena")
    layer = EntitiesLayer([chest, observer], seed=0)
    event = Event(
        event_type=EventType.ENTITY_FLEE,
        source_layer="entities",
        data=EntityFleePayload(
            entity_id=entity_id,
            destination_id="road",
            departed_at_seconds=0,
            arrival_at_seconds=60,
        ),
    )

    result = layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

    assert not result.success
    assert result.error == f"Creature '{entity_id}' not found."
    assert result.events == []
    assert layer.get_entity(chest.id) is chest
    assert chest.location_id == "arena"
    assert layer.get_new_raw_events(observer) == []
    assert layer.get_combat("arena") is None


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("entity_type", "monster", "Input tag 'monster'"),
        ("conditions", ["poisoned"], "Input should be a valid dictionary"),
    ],
)
def test_load_state_rejects_unsupported_save_shapes(field: str, value: object, error: str) -> None:
    guard = Character(id="guard", name="Guard", location_id="arena", max_hp=12, current_hp=7)
    source = EntitiesLayer([guard], seed=0)
    state = source.get_state()
    entities = state["entities"]
    assert isinstance(entities, dict)
    entities[guard.id][field] = value
    restored = EntitiesLayer(seed=0)

    with pytest.raises(ValidationError, match=error):
        restored.load_state(state)

    assert restored.get_entity(guard.id) is None
