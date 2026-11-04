"""Edge-case tests for squad movement functions (layers/ecology/movement.py)."""

from __future__ import annotations

import random

from dnd_simulator.core.location import Location, LocationEdge, LocationGraph
from dnd_simulator.core.squad import Squad, SquadBehavior, SquadType
from dnd_simulator.layers.ecology.movement import move_squad


def _squad(behavior: SquadBehavior, location: str = "A", route: list[str] | None = None) -> Squad:
    return Squad(
        id="s1",
        name="Squad",
        faction_id="f",
        squad_type=SquadType.PATROL,
        behavior=behavior,
        current_location_id=location,
        route=route if route is not None else [],
        territory=["A", "B"],
        strength=10,
        max_strength=10,
        member_templates=[],
        tick_interval=3600,
    )


def _graph() -> LocationGraph:
    def loc(lid: str, edges: list[str]) -> Location:
        return Location(
            id=lid,
            name=lid,
            region_id="r",
            edges=tuple(LocationEdge(target_id=t, distance_m=1000) for t in edges),
        )

    return LocationGraph([loc("A", ["B"]), loc("B", ["A", "X"]), loc("X", ["B", "Y"]), loc("Y", ["X"])])


def _move(squad: Squad, graph: LocationGraph | None = None) -> tuple[str, str] | None:
    return move_squad(squad, {}, {}, graph, random.Random(0))


class TestMoveSquadEdgeCases:
    def test_guard_never_moves(self) -> None:
        squad = _squad(SquadBehavior.GUARD, route=["A", "B"])
        assert _move(squad, _graph()) is None
        assert squad.current_location_id == "A"

    def test_route_behavior_without_route_stays(self) -> None:
        squad = _squad(SquadBehavior.PATROL, route=[])
        assert _move(squad) is None
        assert squad.current_location_id == "A"

    def test_off_route_squad_starts_from_route_head(self) -> None:
        squad = _squad(SquadBehavior.TRADE, location="Z", route=["A", "B", "C"])
        route_index: dict[str, int] = {}
        route_direction: dict[str, int] = {}
        moved = move_squad(squad, route_index, route_direction, None, random.Random(0))
        assert moved == ("Z", "B")
        assert route_index["s1"] == 1
        assert route_direction["s1"] == 1

    def test_single_location_route_stays(self) -> None:
        squad = _squad(SquadBehavior.PATROL, route=["A"])
        assert _move(squad) is None
        assert squad.current_location_id == "A"

    def test_roam_without_graph_stays(self) -> None:
        squad = _squad(SquadBehavior.ROAM)
        assert _move(squad, None) is None

    def test_roam_without_neighbours_in_territory_stays(self) -> None:
        squad = _squad(SquadBehavior.HUNT, location="Y")
        assert _move(squad, _graph()) is None
        assert squad.current_location_id == "Y"

    def test_raid_moves_within_territory(self) -> None:
        squad = _squad(SquadBehavior.RAID, location="B")
        assert _move(squad, _graph()) == ("B", "A")
