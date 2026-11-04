"""Coverage for event location fallbacks and perception boundaries."""

from __future__ import annotations

import pytest

from dnd_simulator.core.character import Character, Creature, Race
from dnd_simulator.core.events import EntitySayPayload, SquadMovePayload
from dnd_simulator.core.inner_self import PERCEIVED_EVENT_BUFFER_CAPACITY, DigestBoundary, InnerSelf
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.layers.entities.event_log import EventLog


def _say(text: str, observer_ids: frozenset[str] | None = None) -> Event:
    return Event(
        event_type=EventType.ENTITY_SAY,
        source_layer="entities",
        data=EntitySayPayload(entity_id="speaker", text=text),
        observer_ids=observer_ids,
    )


@pytest.mark.parametrize(
    ("from_location", "to_location", "expected"),
    [
        ("swamp", "forest_road", "forest_road"),
        ("swamp", "", "swamp"),
        ("", "forest_road", "forest_road"),
    ],
)
def test_squad_move_location_prefers_destination_and_falls_back_to_origin(
    from_location: str, to_location: str, expected: str
) -> None:
    event = Event(
        event_type=EventType.SQUAD_MOVE,
        source_layer="ecology",
        data=SquadMovePayload("orc_patrol", "Orc Patrol", from_location, to_location),
    )

    assert EventLog({}).location_for(event) == expected


def test_digest_can_remove_inner_self_without_buffering_into_detached_core() -> None:
    original_core = InnerSelf()
    witness = Creature(id="witness", name="Witness", location_id="square", inner_self=original_core)
    speaker = Creature(id="speaker", name="Speaker", location_id="square")
    location_log: dict[str, list[Event]] = {}

    def remove_inner_self(creature: Creature, boundary: DigestBoundary) -> None:
        assert boundary is DigestBoundary.BUFFER_FULL
        creature.inner_self = None

    log = EventLog({entity.id: entity for entity in (witness, speaker)}, location_log, digest=remove_inner_self)
    events = [_say(str(index)) for index in range(PERCEIVED_EVENT_BUFFER_CAPACITY + 1)]

    for event in events:
        log.record(event)

    assert witness.inner_self is None
    assert [event.description for event in original_core.perceived_event_buffer] == [
        f'Speaker says: "{index}"' for index in range(PERCEIVED_EVENT_BUFFER_CAPACITY)
    ]
    assert location_log == {"square": events}


@pytest.mark.parametrize(
    ("observer_ids", "visible"),
    [
        (None, True),
        (frozenset({"player_1"}), True),
        (frozenset({"someone-else"}), False),
        (frozenset(), False),
    ],
)
def test_perceived_events_filter_observers_and_consume_unread_events(
    observer_ids: frozenset[str] | None, visible: bool
) -> None:
    player = Character(id="player_1", name="Hero", location_id="square", race=Race.HUMAN)
    speaker = Creature(id="speaker", name="Speaker", location_id="square")
    entities = {entity.id: entity for entity in (player, speaker)}
    log = EventLog(entities)
    log.record(_say("Secret", observer_ids))
    log.record(_say("Hello"))

    perceived = log.perceived_events(player, entities.get)

    expected = ['Speaker says: "Secret"', 'Speaker says: "Hello"'] if visible else ['Speaker says: "Hello"']
    assert [event.description for event in perceived] == expected
    assert log.perceived_events(player, entities.get) == []

    log.record(_say("Next"))
    assert [event.description for event in log.perceived_events(player, entities.get)] == ['Speaker says: "Next"']
