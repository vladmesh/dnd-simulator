"""Coverage for location lookups, missing edges, and shortest-route queue handling."""

import pytest

from dnd_simulator.core.location import Location, LocationEdge, LocationGraph


@pytest.mark.parametrize("from_id, to_id", [("mill", "tavern"), ("gate", "mill"), ("tavern", "mill")])
def test_travel_requires_a_direct_edge(from_id: str, to_id: str) -> None:
    graph = LocationGraph(
        [
            Location("mill", "Old Mill", "greenvale", edges=(LocationEdge("gate", 1000),)),
            Location("gate", "Gate", "greenvale", edges=(LocationEdge("tavern", 500),)),
            Location("tavern", "Tavern", "greenvale"),
        ]
    )

    assert graph.edge_between(from_id, to_id) is None
    with pytest.raises(ValueError, match=f"^No direct path from '{from_id}' to '{to_id}'$"):
        graph.travel_seconds(from_id, to_id)


def test_shortest_route_discards_superseded_queue_entries() -> None:
    graph = LocationGraph(
        [
            Location(
                "mill",
                "Old Mill",
                "greenvale",
                edges=(LocationEdge("gate", 1000), LocationEdge("bridge", 100)),
            ),
            Location("bridge", "Bridge", "greenvale", edges=(LocationEdge("gate", 100),)),
            Location("gate", "Gate", "greenvale", edges=(LocationEdge("tavern", 2000),)),
            Location("tavern", "Tavern", "greenvale"),
        ]
    )

    assert graph.shortest_route("mill", "tavern") == ("bridge", "gate", "tavern")


def test_shortest_route_ignores_edges_to_unknown_locations() -> None:
    graph = LocationGraph(
        [
            Location(
                "mill",
                "Old Mill",
                "greenvale",
                edges=(LocationEdge("abandoned", 1), LocationEdge("gate", 1000)),
            ),
            Location("gate", "Gate", "greenvale", edges=(LocationEdge("tavern", 500),)),
            Location("tavern", "Tavern", "greenvale"),
        ]
    )

    assert graph.shortest_route("mill", "tavern") == ("gate", "tavern")


def test_shortest_route_with_only_unknown_neighbors_reports_no_route() -> None:
    graph = LocationGraph(
        [
            Location("mill", "Old Mill", "greenvale", edges=(LocationEdge("abandoned", 100),)),
            Location("tavern", "Tavern", "greenvale"),
        ]
    )

    with pytest.raises(ValueError, match=r"^No route from 'mill' to 'tavern'$"):
        graph.shortest_route("mill", "tavern")


@pytest.mark.parametrize(
    "from_id, to_id, message",
    [
        ("missing", "mill", "Unknown route origin 'missing'"),
        ("mill", "missing", "Unknown route destination 'missing'"),
    ],
)
def test_shortest_route_rejects_unknown_endpoints(from_id: str, to_id: str, message: str) -> None:
    graph = LocationGraph([Location("mill", "Old Mill", "greenvale")])

    with pytest.raises(ValueError, match=f"^{message}$"):
        graph.shortest_route(from_id, to_id)


def test_shortest_route_to_current_location_is_empty() -> None:
    graph = LocationGraph([Location("mill", "Old Mill", "greenvale")])

    assert graph.shortest_route("mill", "mill") == ()


@pytest.mark.parametrize(
    "locations, expected_ids",
    [
        ([], []),
        (
            [Location("mill", "Old Mill", "greenvale"), Location("gate", "Gate", "greenvale")],
            ["mill", "gate"],
        ),
    ],
)
def test_all_ids_lists_locations_in_insertion_order(locations: list[Location], expected_ids: list[str]) -> None:
    graph = LocationGraph(locations)

    assert graph.all_ids() == expected_ids
