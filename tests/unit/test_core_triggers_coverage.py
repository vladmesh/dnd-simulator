"""Coverage for event-condition matching and trigger-definition validation."""

import pytest

from dnd_simulator.core.events import WarDeclaredPayload
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.core.triggers import EventCondition, TriggerDefinition


@pytest.mark.parametrize(
    ("event_type", "match_fields", "expected"),
    [
        (EventType.WAR_DECLARED, {"aggressor_id": "north", "target_id": "south"}, True),
        (EventType.WAR_DECLARED, {"aggressor_id": "south", "target_id": "north"}, False),
        (EventType.PEACE_DECLARED, {"nation_a_id": "north", "nation_b_id": "south"}, False),
    ],
    ids=["matching-payload", "different-payload", "different-event-type"],
)
def test_event_condition_matches(event_type: EventType, match_fields: dict[str, object], expected: bool) -> None:
    condition = EventCondition.from_mapping(event_type, match_fields)
    event = Event(EventType.WAR_DECLARED, "politics", WarDeclaredPayload("north", "south"))

    assert condition.matches(event) is expected


@pytest.mark.parametrize("trigger_id", ["", " ", "\t\n"])
def test_trigger_definition_rejects_blank_id(trigger_id: str) -> None:
    on = EventCondition(EventType.WAR_DECLARED)
    until = EventCondition(EventType.PEACE_DECLARED)

    with pytest.raises(ValueError, match=r"^trigger id must not be empty$"):
        TriggerDefinition(id=trigger_id, on=on, until=until)
