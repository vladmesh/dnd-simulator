"""Squad movement descriptions depend on the observer's location."""

import pytest

from dnd_simulator.core.character import Character
from dnd_simulator.core.events import SquadMovePayload
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.i18n import set_language
from dnd_simulator.layers.entities.perception_world import squad_move


@pytest.mark.parametrize(
    ("observer_location", "expected"),
    [
        ("forest_road", "Orc Patrol arrives"),
        ("swamp", "Orc Patrol departs"),
        ("distant_cave", "Orc Patrol is on the move"),
    ],
)
def test_squad_move_description(observer_location: str, expected: str) -> None:
    set_language("en")
    observer = Character(id="player_1", name="Hero", location_id=observer_location)
    entities = {observer.id: observer}
    event = Event(
        event_type=EventType.SQUAD_MOVE,
        source_layer="ecology",
        data=SquadMovePayload("orc_patrol", "Orc Patrol", "swamp", "forest_road"),
    )

    assert squad_move(event, observer, entities.get) == expected
