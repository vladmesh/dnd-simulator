"""Coverage for rejected events propagated through World."""

import pytest

from dnd_simulator.core.character import Character
from dnd_simulator.core.events import AttackRequestedPayload
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer


@pytest.mark.parametrize(
    ("attacker_id", "target_id", "error"),
    [
        ("missing", "hero", "Attacker 'missing' not found."),
        ("hero", "missing", "Target 'missing' not found."),
    ],
)
def test_handle_event_returns_layer_rejection(attacker_id: str, target_id: str, error: str) -> None:
    hero = Character(id="hero", name="Hero", location_id="arena", max_hp=20, current_hp=20)
    world = World(layers=[EntitiesLayer([hero])])
    event = Event(
        event_type=EventType.ENTITY_ATTACK_REQUESTED,
        source_layer="entities",
        data=AttackRequestedPayload(attacker_id=attacker_id, target_id=target_id),
    )

    result = world.handle_event(event)

    assert result == ActionResult(success=False, error=error)
    assert hero.current_hp == 20
    assert not hero.in_combat
