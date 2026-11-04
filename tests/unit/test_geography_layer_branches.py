"""Branch coverage for layers/geography/layer.py: travel time and day/night resolution edge cases."""

from __future__ import annotations

from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import Query, QueryType
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType


def _regions() -> list[Region]:
    return [
        Region(
            id="lowland",
            name="Lowland",
            latitude=45.0,
            longitude=10.0,
            elevation=100.0,
            terrain=TerrainType.PLAINS,
            water_proximity=0.5,
        ),
        Region(
            id="highland",
            name="Highland",
            latitude=45.5,
            longitude=10.0,
            elevation=1100.0,
            terrain=TerrainType.MOUNTAINS,
            water_proximity=0.0,
        ),
    ]


class TestTravelTime:
    def test_uphill_travel_reports_distance_and_hours(self) -> None:
        layer = GeographyLayer(regions=_regions())

        answer = layer.query(Query(question=QueryType.TRAVEL_TIME, params={"from_id": "lowland", "to_id": "highland"}))

        assert isinstance(answer.value, dict)
        assert answer.value["distance_km"] > 0
        assert answer.value["hours"] > 0
        assert "km" in answer.description


class TestIsDaylightResolution:
    def test_unknown_location_degrades_to_daytime(self) -> None:
        graph = LocationGraph([Location(id="gate", name="Gate", region_id="lowland")])
        layer = GeographyLayer(regions=_regions(), location_graph=graph)

        answer = layer.query(
            Query(question=QueryType.IS_DAYLIGHT, params={"location_id": "nowhere", "month": 6, "hour": 0})
        )

        assert answer.value is True

    def test_known_location_resolves_night(self) -> None:
        graph = LocationGraph([Location(id="gate", name="Gate", region_id="lowland")])
        layer = GeographyLayer(regions=_regions(), location_graph=graph)

        answer = layer.query(
            Query(question=QueryType.IS_DAYLIGHT, params={"location_id": "gate", "month": 6, "hour": 0})
        )

        assert answer.value is False
        assert answer.description == "night"
