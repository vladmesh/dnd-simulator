"""Product-level navigation behavior over the world location graph."""

import pytest

from dnd_simulator.core.location import Location, LocationEdge, LocationGraph


def _graph() -> LocationGraph:
    return LocationGraph(
        [
            Location(
                id="start",
                name="Start",
                region_id="r",
                edges=(LocationEdge("long", 5), LocationEdge("alpha", 2), LocationEdge("beta", 2)),
            ),
            Location(id="long", name="Long Road", region_id="r", edges=(LocationEdge("goal", 5),)),
            Location(id="alpha", name="Alpha Road", region_id="r", edges=(LocationEdge("goal", 3),)),
            Location(id="beta", name="Beta Road", region_id="r", edges=(LocationEdge("goal", 3),)),
            Location(id="goal", name="Goal", region_id="r"),
            Location(id="island", name="Island", region_id="r"),
        ]
    )


def test_shortest_route_uses_total_distance_and_stable_tie_breaking() -> None:
    graph = _graph()

    assert graph.shortest_route("start", "goal") == ("alpha", "goal")


@pytest.mark.parametrize(("start", "destination"), [("missing", "goal"), ("start", "missing"), ("start", "island")])
def test_shortest_route_rejects_unknown_or_unreachable_destinations(start: str, destination: str) -> None:
    with pytest.raises(ValueError):
        _graph().shortest_route(start, destination)
