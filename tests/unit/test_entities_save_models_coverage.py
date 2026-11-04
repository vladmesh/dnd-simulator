"""Validation boundaries for entity save-state models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dnd_simulator.core.inner_self import GoalStatus, RelationshipType
from dnd_simulator.core.intent import IntentType
from dnd_simulator.layers.entities.save_models import CreatureSave, GoalSave, InnerSelfSave, TravelIntentSave


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "protect", "target_id": "ally"},
        {"text": "Find a quiet place to think"},
    ],
)
def test_goal_accepts_typed_or_freeform_shape(payload: dict[str, str]) -> None:
    goal = GoalSave.model_validate(payload)

    assert goal.model_dump(mode="json", exclude_none=True) == {**payload, "status": GoalStatus.ACTIVE.value}
    assert GoalSave.model_validate_json(goal.model_dump_json()) == goal


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"type": "protect"},
        {"type": "protect", "target_id": ""},
        {"target_id": "ally"},
        {"text": ""},
        {"type": "protect", "target_id": "ally", "text": "Protect my ally"},
        {"type": "protect", "target_id": "ally", "text": ""},
        {"target_id": "ally", "text": "Protect my ally"},
        {"type": "protect", "text": "Protect my ally"},
    ],
)
def test_goal_rejects_incomplete_or_mixed_shapes(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError, match=r"goal must be typed \(type \+ target_id\) or freeform \(text\)"):
        GoalSave.model_validate(payload)


@pytest.mark.parametrize("second_intensity", [50, 75])
def test_inner_self_rejects_duplicate_relationship_key(second_intensity: int) -> None:
    with pytest.raises(ValidationError, match="duplicate relationship type for target"):
        InnerSelfSave.model_validate(
            {
                "relations": [
                    {"target_id": "ally", "type": "trusts", "intensity": 50},
                    {"target_id": "ally", "type": "trusts", "intensity": second_intensity},
                ]
            }
        )


@pytest.mark.parametrize(
    ("second_target", "second_type"),
    [("ally", RelationshipType.LOYAL_TO), ("another_ally", RelationshipType.TRUSTS)],
)
def test_inner_self_allows_relationships_with_distinct_keys(second_target: str, second_type: RelationshipType) -> None:
    relations = [
        {"target_id": "ally", "type": "trusts", "intensity": 50},
        {"target_id": second_target, "type": second_type.value, "intensity": 75},
    ]

    inner_self = InnerSelfSave.model_validate({"relations": relations})

    assert inner_self.model_dump(mode="json")["relations"] == relations


@pytest.mark.parametrize(
    ("destination_id", "arrival", "message"),
    [
        ("elsewhere", 110, "travel destination must be the final route node"),
        ("keep", 99, "arrival time cannot precede journey start time"),
    ],
)
def test_travel_intent_rejects_inconsistent_route_or_time(destination_id: str, arrival: int, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        TravelIntentSave(
            kind=IntentType.TRAVEL,
            started_at_seconds=100,
            destination_id=destination_id,
            remaining_route=("crossroads", "keep"),
            next_arrival_seconds=arrival,
        )


@pytest.mark.parametrize("arrival", [100, 110])
def test_travel_intent_accepts_arrival_at_or_after_start(arrival: int) -> None:
    intent = TravelIntentSave(
        kind=IntentType.TRAVEL,
        started_at_seconds=100,
        destination_id="keep",
        remaining_route=("crossroads", "keep"),
        next_arrival_seconds=arrival,
    )

    assert intent.model_dump(mode="json") == {
        "kind": "travel",
        "started_at_seconds": 100,
        "destination_id": "keep",
        "remaining_route": ["crossroads", "keep"],
        "next_arrival_seconds": arrival,
        "fleeing": False,
    }
    assert TravelIntentSave.model_validate_json(intent.model_dump_json()) == intent


def _creature_payload(trigger_ids: tuple[str, ...]) -> dict[str, object]:
    return {
        "entity_type": "creature",
        "id": "guard",
        "name": "Guard",
        "location_id": "far_keep",
        "active": True,
        "max_hp": 10,
        "current_hp": 10,
        "ac": 12,
        "speed": 30,
        "ability_scores": {},
        "triggers": [
            {
                "id": trigger_id,
                "on": {
                    "event": "war_declared",
                    "match": {"aggressor_id": "north", "target_id": "south"},
                },
                "until": {
                    "event": "peace_declared",
                    "match": {"nation_a_id": "north", "nation_b_id": "south"},
                },
            }
            for trigger_id in trigger_ids
        ],
    }


def test_creature_rejects_duplicate_trigger_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate trigger id"):
        CreatureSave.model_validate(_creature_payload(("war_duty", "war_duty")))


@pytest.mark.parametrize("trigger_ids", [(), ("war_duty",), ("war_duty", "second_duty")])
def test_creature_accepts_unique_trigger_ids(trigger_ids: tuple[str, ...]) -> None:
    creature = CreatureSave.model_validate(_creature_payload(trigger_ids))

    assert tuple(trigger.id for trigger in creature.triggers) == trigger_ids
    assert all(trigger.armed and not trigger.active for trigger in creature.triggers)
    assert CreatureSave.model_validate_json(creature.model_dump_json()) == creature
