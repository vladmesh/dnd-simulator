"""Coverage for character queries of unread perceived events."""

from dnd_simulator.core.character import Character
from dnd_simulator.core.events import EntitySayPayload
from dnd_simulator.core.models import Event, EventType, Query, QueryType
from dnd_simulator.layers.entities.layer import EntitiesLayer


def test_new_perceived_events_filters_private_events_and_marks_log_read() -> None:
    observer = Character(id="observer", name="Observer", location_id="square")
    speaker = Character(id="speaker", name="Speaker", location_id="square")
    layer = EntitiesLayer([observer, speaker], seed=0)
    layer._location_log["square"].extend(
        [
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data=EntitySayPayload(entity_id=speaker.id, text="Hello everyone!"),
            ),
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data=EntitySayPayload(entity_id=speaker.id, text="Secret whisper"),
                observer_ids=frozenset({speaker.id}),
            ),
        ]
    )
    query = Query(question=QueryType.NEW_PERCEIVED_EVENTS, params={"entity_id": observer.id})

    perceived = layer.query(query).value

    assert isinstance(perceived, list)
    assert len(perceived) == 1
    assert "Hello everyone!" in perceived[0]
    assert layer.query(query).value == []
