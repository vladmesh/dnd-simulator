"""Product-level contract tests for creature activation trigger tables."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dnd_simulator.content_loader import parse_npc
from dnd_simulator.core.events import EventPayload, PeaceDeclaredPayload, WarDeclaredPayload
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.layers.entities.layer import EntitiesLayer


def _npc_data(*, triggers: list[dict[str, object]], always_active: bool = False) -> dict[str, object]:
    return {
        "name": "Prince Arlen",
        "start_location": "palace",
        "always_active": always_active,
        "triggers": triggers,
    }


def _war_duty(
    *,
    trigger_id: str = "war_duty",
    armed: bool = True,
    aggressor_id: str = "north",
    target_id: str = "south",
) -> dict[str, object]:
    return {
        "id": trigger_id,
        "armed": armed,
        "on": {
            "event": "war_declared",
            "match": {"aggressor_id": aggressor_id, "target_id": target_id},
        },
        "until": {
            "event": "peace_declared",
            "match": {"nation_a_id": "north", "nation_b_id": "south"},
        },
    }


def _event(event_type: EventType, payload: EventPayload) -> Event:
    return Event(event_type=event_type, source_layer="politics", data=payload)


def test_named_npc_loads_typed_trigger_pair_from_content() -> None:
    npc = parse_npc("prince", _npc_data(triggers=[_war_duty()], always_active=True))

    assert npc.always_active is True
    assert len(npc.triggers) == 1
    trigger = npc.triggers[0]
    assert trigger.definition.id == "war_duty"
    assert trigger.definition.on.event_type is EventType.WAR_DECLARED
    assert trigger.definition.on.match_fields == (
        ("aggressor_id", "north"),
        ("target_id", "south"),
    )
    assert trigger.definition.until.event_type is EventType.PEACE_DECLARED
    assert trigger.armed is True
    assert trigger.active is False


def test_trigger_index_matches_typed_payload_subset_without_changing_activity() -> None:
    prince = parse_npc("prince", _npc_data(triggers=[_war_duty()]))
    prince.active = False
    layer = EntitiesLayer([prince])

    matches = layer.find_trigger_matches(
        _event(EventType.WAR_DECLARED, WarDeclaredPayload(aggressor_id="north", target_id="south"))
    )
    other_war = layer.find_trigger_matches(
        _event(EventType.WAR_DECLARED, WarDeclaredPayload(aggressor_id="east", target_id="south"))
    )
    peace = layer.find_trigger_matches(
        _event(EventType.PEACE_DECLARED, PeaceDeclaredPayload(nation_a_id="north", nation_b_id="south"))
    )

    assert [(match.creature.id, match.trigger.definition.id, match.boundary.value) for match in matches] == [
        ("prince", "war_duty", "on")
    ]
    assert other_war == []
    assert [(match.creature.id, match.boundary.value) for match in peace] == [("prince", "until")]
    assert prince.active is False
    assert prince.triggers[0].active is False


def test_condition_without_fields_matches_every_event_of_its_type() -> None:
    herald = parse_npc(
        "herald",
        _npc_data(
            triggers=[
                {
                    "id": "any_war",
                    "on": {"event": "war_declared"},
                    "until": {"event": "peace_declared"},
                }
            ]
        ),
    )
    layer = EntitiesLayer([herald])

    matches = layer.find_trigger_matches(
        _event(EventType.WAR_DECLARED, WarDeclaredPayload(aggressor_id="east", target_id="west"))
    )

    assert [(match.creature.id, match.trigger.definition.id) for match in matches] == [("herald", "any_war")]


def test_index_tracks_multiple_creatures_and_add_remove() -> None:
    prince = parse_npc("prince", _npc_data(triggers=[_war_duty()]))
    spectator = parse_npc(
        "spectator",
        _npc_data(triggers=[_war_duty(trigger_id="other_war", aggressor_id="east", target_id="west")]),
    )
    disarmed = parse_npc("disarmed", _npc_data(triggers=[_war_duty(trigger_id="held", armed=False)]))
    late_arrival = parse_npc("late", _npc_data(triggers=[_war_duty(trigger_id="late_war")]))
    layer = EntitiesLayer([prince, spectator, disarmed])
    war = _event(EventType.WAR_DECLARED, WarDeclaredPayload(aggressor_id="north", target_id="south"))

    assert [match.creature.id for match in layer.find_trigger_matches(war)] == ["prince"]

    layer.add_entity(late_arrival)
    assert [match.creature.id for match in layer.find_trigger_matches(war)] == ["prince", "late"]

    layer.remove_entity("prince")
    assert [match.creature.id for match in layer.find_trigger_matches(war)] == ["late"]


@pytest.mark.parametrize(
    ("triggers", "message"),
    [
        (
            [
                {
                    "id": "bad_event",
                    "on": {"event": "not_a_world_event"},
                    "until": {"event": "peace_declared"},
                }
            ],
            "not_a_world_event",
        ),
        ([_war_duty(), _war_duty()], "duplicate trigger id"),
        (
            [
                {
                    "id": "bad_field",
                    "on": {"event": "war_declared", "match": {"nation_id": "north"}},
                    "until": {"event": "peace_declared"},
                }
            ],
            "nation_id",
        ),
        (
            [
                {
                    "id": "bad_value",
                    "on": {"event": "war_declared", "match": {"aggressor_id": 42}},
                    "until": {"event": "peace_declared"},
                }
            ],
            "aggressor_id",
        ),
    ],
)
def test_invalid_trigger_content_fails_at_load_boundary(triggers: list[dict[str, object]], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_npc("prince", _npc_data(triggers=triggers))
