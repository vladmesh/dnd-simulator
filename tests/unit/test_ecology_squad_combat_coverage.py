"""Coverage for squad combat pairing, outcomes, and destroyed-squad cleanup."""

from __future__ import annotations

import random

import pytest

from dnd_simulator.core.events import SquadCombatPayload
from dnd_simulator.core.location import Location, LocationEdge, LocationGraph
from dnd_simulator.core.models import Answer, EventType, FactionRelation, Query
from dnd_simulator.core.squad import Squad, SquadBehavior, SquadType
from dnd_simulator.layers.ecology.squad_combat import resolve_squad_combat


def _make_squad(
    squad_id: str,
    faction: str,
    strength: int = 10,
    member_cr: float = 2.0,
    location: str = "road_north",
) -> Squad:
    return Squad(
        id=squad_id,
        name=f"Squad {squad_id}",
        faction_id=faction,
        squad_type=SquadType.PATROL,
        behavior=SquadBehavior.PATROL,
        current_location_id=location,
        route=["road_north", "road_south"],
        territory=["road_north", "road_south"],
        strength=strength,
        max_strength=strength,
        member_templates=["bandit"],
        tick_interval=3600,
        member_crs=[member_cr],
    )


def _hostile_query(layer: str, query: Query) -> Answer:
    return Answer(value=FactionRelation.HOSTILE)


def test_each_squad_fights_once_and_skips_its_own_faction() -> None:
    squads = {
        squad.id: squad
        for squad in (
            _make_squad("guard_1", "kingdom"),
            _make_squad("guard_2", "kingdom"),
            _make_squad("raider_1", "raiders"),
            _make_squad("raider_2", "raiders"),
        )
    }

    events = resolve_squad_combat(squads, None, {}, {}, {}, _hostile_query, random.Random(0))

    assert [event.payload for event in events] == [
        SquadCombatPayload("road_north", f"guard_{i}", f"Squad guard_{i}", f"raider_{i}", f"Squad raider_{i}", 9, 9)
        for i in (1, 2)
    ]
    assert all(event.event_type is EventType.SQUAD_COMBAT for event in events)
    assert all(event.source_layer == "ecology" for event in events)
    assert {squad_id: squad.strength for squad_id, squad in squads.items()} == {
        "guard_1": 9,
        "guard_2": 9,
        "raider_1": 9,
        "raider_2": 9,
    }


@pytest.mark.parametrize("weak_first", [True, False])
def test_weaker_squad_loses_strength_and_retreats(weak_first: bool) -> None:
    weak = _make_squad("weak", "kingdom", strength=4, member_cr=1.0)
    strong = _make_squad("strong", "raiders", strength=10, member_cr=6.0)
    ordered = (weak, strong) if weak_first else (strong, weak)
    squads = {squad.id: squad for squad in ordered}
    graph = LocationGraph(
        [
            Location(
                id="road_north",
                name="North Road",
                region_id="forest",
                edges=(LocationEdge(target_id="road_south", distance_m=100),),
            ),
            Location(id="road_south", name="South Road", region_id="forest"),
        ]
    )

    events = resolve_squad_combat(squads, graph, {}, {}, {}, _hostile_query, random.Random(0))

    assert len(events) == 1
    assert events[0].payload == SquadCombatPayload("road_north", "strong", "Squad strong", "weak", "Squad weak", 9, 2)
    assert events[0].description == "Squad strong defeated Squad weak at road_north"
    assert strong.strength == 9
    assert weak.strength == 2
    assert strong.current_location_id == "road_north"
    assert weak.current_location_id == "road_south"
    assert set(squads) == {"weak", "strong"}


@pytest.mark.parametrize("tracked", [True, False])
def test_destroyed_squad_is_removed_from_squads_and_movement_tracking(tracked: bool) -> None:
    survivor = _make_squad("survivor", "kingdom")
    destroyed = _make_squad("destroyed", "raiders", strength=0, location="road_south")
    squads = {squad.id: squad for squad in (survivor, destroyed)}
    last_move_time = {"survivor": 3600}
    route_index = {"survivor": 1}
    route_direction = {"survivor": -1}
    if tracked:
        last_move_time["destroyed"] = 1800
        route_index["destroyed"] = 0
        route_direction["destroyed"] = 1

    events = resolve_squad_combat(
        squads, None, last_move_time, route_index, route_direction, _hostile_query, random.Random(0)
    )

    assert events == []
    assert squads == {"survivor": survivor}
    assert survivor.strength == 10
    assert survivor.current_location_id == "road_north"
    assert last_move_time == {"survivor": 3600}
    assert route_index == {"survivor": 1}
    assert route_direction == {"survivor": -1}
