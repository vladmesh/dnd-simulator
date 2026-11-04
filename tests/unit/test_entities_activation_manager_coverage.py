"""Coverage for travel validation and scheduled NPC activation."""

import pytest

from dnd_simulator.core.character import Creature
from dnd_simulator.core.intent import TravelIntent
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc, NpcActivity, ScheduleEntry

_TIME = GameDateTime(year=1490, month=6, day=1, hour=12)


@pytest.mark.parametrize("arrival_offset", [-60, 0])
def test_due_travel_requires_location_graph(arrival_offset: int) -> None:
    now = _TIME.to_total_seconds()
    intent = TravelIntent(now - 600, "goal", ("goal",), now + arrival_offset)
    traveler = Creature(id="traveler", name="Traveler", location_id="start", current_intent=intent)
    layer = EntitiesLayer([traveler], seed=0)

    with pytest.raises(RuntimeError, match=r"^location graph is required to advance travel$"):
        layer.update_activation(_TIME)

    assert traveler.location_id == "start"
    assert traveler.current_intent == intent


def test_pending_travel_does_not_require_location_graph() -> None:
    now = _TIME.to_total_seconds()
    intent = TravelIntent(now, "goal", ("goal",), now + 60)
    traveler = Creature(
        id="traveler", name="Traveler", location_id="start", current_intent=intent, is_anchor=True, active=True
    )
    layer = EntitiesLayer([traveler], seed=0)

    layer.update_activation(_TIME)

    assert traveler.location_id == "start"
    assert traveler.current_intent == intent
    assert traveler.active is False


@pytest.mark.parametrize("anchor_at_work", [True, False])
def test_npc_moves_to_scheduled_location_only_when_activated(anchor_at_work: bool) -> None:
    npc = Npc(
        id="smith",
        name="Smith",
        location_id="home",
        active=not anchor_at_work,
        schedule=[ScheduleEntry(8, 18, NpcActivity.WORKING, "smithy")],
    )
    anchor = Creature(id="anchor", name="Anchor", location_id="smithy" if anchor_at_work else "square", is_anchor=True)
    layer = EntitiesLayer([anchor, npc], seed=0)

    layer.update_activation(_TIME)

    assert npc.active is anchor_at_work
    assert npc.location_id == ("smithy" if anchor_at_work else "home")
    assert layer.get_active_creatures() == ([anchor, npc] if anchor_at_work else [anchor])
