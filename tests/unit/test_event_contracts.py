from __future__ import annotations

import pytest

from dnd_simulator.core.events import (
    EVENT_PAYLOAD_TYPES,
    AttackRequestedPayload,
    AttackResolvedPayload,
    CombatStartedPayload,
    EncounterSpawnedPayload,
    EntityDiedPayload,
    EntityMovePayload,
    SquadMaterializedPayload,
    SquadMovePayload,
    WeatherChangedPayload,
    XpGainedPayload,
)
from dnd_simulator.core.models import Event, EventType


def test_typed_weather_and_squad_payloads_expose_domain_fields() -> None:
    weather = Event(
        event_type=EventType.WEATHER_CHANGED,
        source_layer="geography",
        data=WeatherChangedPayload("north", "clear", "rain", 8.5),
    )
    move = Event(
        event_type=EventType.SQUAD_MOVE,
        source_layer="ecology",
        data=SquadMovePayload("wolves", "Wolf Pack", "forest", "road"),
    )
    materialized = Event(
        event_type=EventType.SQUAD_MATERIALIZED,
        source_layer="entities",
        data=SquadMaterializedPayload("wolves", "Wolf Pack", "road", 3),
    )

    assert weather.data.new_weather == "rain"
    assert move.data.to_location_id == "road"
    assert materialized.data.creature_count == 3


def test_event_rejects_payload_for_another_event_type() -> None:
    with pytest.raises(TypeError, match=r"SQUAD_MOVE.*WeatherChangedPayload"):
        Event(
            event_type=EventType.SQUAD_MOVE,
            source_layer="ecology",
            data=WeatherChangedPayload("north", "clear", "rain", 8.5),
        )


def test_lifecycle_payloads_expose_stable_ids_and_combat_state() -> None:
    encounter = Event(
        EventType.ENCOUNTER_SPAWNED,
        "entities",
        EncounterSpawnedPayload("crossroads", ("Goblin", "Goblin"), ("goblin_1", "goblin_2")),
    )
    combat = Event(
        EventType.COMBAT_STARTED,
        "entities",
        CombatStartedPayload("crossroads", ("hero", "goblin_1"), ("Hero", "Goblin")),
    )
    death = Event(EventType.ENTITY_DIED, "entities", EntityDiedPayload("goblin_1", "crossroads", "hero"))
    movement = Event(
        EventType.ENTITY_MOVE,
        "entities",
        EntityMovePayload("hero", "crossroads", 0, 0, 5, 0, 5),
    )
    xp = Event(EventType.XP_GAINED, "entities", XpGainedPayload("hero", 50, 50, "goblin_1", False, "crossroads"))

    assert encounter.data.spawned_entity_ids == ("goblin_1", "goblin_2")
    assert combat.data.turn_order == ("hero", "goblin_1")
    assert death.data.killer_id == "hero"
    assert movement.data.distance_ft == 5
    assert xp.data.source_entity_id == "goblin_1"


def test_lifecycle_event_rejects_incompatible_payload_immediately() -> None:
    with pytest.raises(TypeError, match=r"ENTITY_DIED.*EncounterSpawnedPayload"):
        Event(
            EventType.ENTITY_DIED,
            "entities",
            EncounterSpawnedPayload("crossroads", ("Goblin",), ("goblin_1",)),
        )


def test_attack_request_and_result_have_distinct_contracts() -> None:
    requested = Event(
        EventType.ENTITY_ATTACK_REQUESTED,
        "entities",
        AttackRequestedPayload("hero", "goblin", 1),
    )
    resolved = Event(
        EventType.ENTITY_ATTACK,
        "entities",
        AttackResolvedPayload("hero", "goblin", False, "Longsword", False, 13, None),
    )

    assert requested.data.smite_slot_level == 1
    assert resolved.data.hit is False
    with pytest.raises(TypeError, match="ENTITY_ATTACK requires AttackResolvedPayload"):
        Event(EventType.ENTITY_ATTACK, "entities", requested.data)


def test_every_event_type_has_one_payload_contract() -> None:
    assert set(EVENT_PAYLOAD_TYPES) == set(EventType)
