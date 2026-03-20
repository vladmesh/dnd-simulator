"""Tests for the GeographyLayer."""

from dnd_simulator.core.models import EventType, GameDateTime, Query, TimeDelta
from dnd_simulator.core.world import WorldState
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import (
    Connection,
    Direction,
    Region,
    TerrainType,
    WeatherCondition,
)


def _make_test_regions() -> list[Region]:
    return [
        Region(
            id="forest_vale",
            name="Forest Vale",
            latitude=45.0,
            longitude=10.0,
            elevation=200.0,
            terrain=TerrainType.FOREST,
            water_proximity=0.3,
            connections=[Connection(target_id="mountain_pass", direction=Direction.N)],
        ),
        Region(
            id="mountain_pass",
            name="Mountain Pass",
            latitude=47.0,
            longitude=10.0,
            elevation=2500.0,
            terrain=TerrainType.MOUNTAINS,
            water_proximity=0.0,
            connections=[Connection(target_id="forest_vale", direction=Direction.S)],
        ),
    ]


class TestGeographyLayer:
    def test_name(self) -> None:
        layer = GeographyLayer()
        assert layer.name == "geography"

    def test_add_and_get_region(self) -> None:
        layer = GeographyLayer()
        regions = _make_test_regions()
        for r in regions:
            layer.add_region(r)

        region = layer.get_region("forest_vale")
        assert region.name == "Forest Vale"

    def test_get_region_not_found(self) -> None:
        import pytest

        layer = GeographyLayer()
        with pytest.raises(KeyError):
            layer.get_region("nonexistent")

    def test_tick_updates_temperature(self) -> None:
        layer = GeographyLayer(regions=_make_test_regions(), weather_seed=42)
        state = WorldState(time=GameDateTime(year=1490, month=7, day=15, hour=12))
        delta = TimeDelta.from_hours(6)

        layer.tick(delta, state)

        forest = layer.get_region("forest_vale")
        mountain = layer.get_region("mountain_pass")

        # Mountain should be colder due to elevation
        assert mountain.temperature < forest.temperature

    def test_tick_returns_weather_events(self) -> None:
        layer = GeographyLayer(regions=_make_test_regions(), weather_seed=42)
        state = WorldState(time=GameDateTime(year=1490, month=7, day=15, hour=12))

        # Run multiple ticks to get at least some weather changes
        all_events = []
        for _ in range(20):
            events = layer.tick(TimeDelta.from_hours(6), state)
            all_events.extend(events)

        # At least some weather changes should have occurred
        weather_events = [e for e in all_events if e.event_type == EventType.WEATHER_CHANGED]
        assert len(weather_events) > 0

        # Events should have region_id in data
        for event in weather_events:
            assert "region_id" in event.data

    def test_query_weather(self) -> None:
        regions = _make_test_regions()
        regions[0].weather = WeatherCondition.LIGHT_RAIN
        regions[0].temperature = 18.5
        layer = GeographyLayer(regions=regions)

        answer = layer.query(Query(question="weather", params={"region_id": "forest_vale"}))
        assert answer.value["condition"] == "light_rain"
        assert answer.value["temperature"] == 18.5

    def test_query_connections(self) -> None:
        layer = GeographyLayer(regions=_make_test_regions())
        answer = layer.query(Query(question="connections", params={"region_id": "forest_vale"}))

        assert len(answer.value) == 1
        assert answer.value[0]["target_id"] == "mountain_pass"
        assert answer.value[0]["direction"] == "n"

    def test_query_daylight(self) -> None:
        layer = GeographyLayer(regions=_make_test_regions())
        answer = layer.query(Query(question="daylight", params={"region_id": "forest_vale", "month": 6}))
        assert answer.value > 14.0  # Mid-latitude summer = long days

    def test_query_regions(self) -> None:
        layer = GeographyLayer(regions=_make_test_regions())
        answer = layer.query(Query(question="regions", params={}))
        assert set(answer.value) == {"forest_vale", "mountain_pass"}

    def test_query_unknown_raises(self) -> None:
        import pytest

        layer = GeographyLayer(regions=_make_test_regions())
        with pytest.raises(ValueError):
            layer.query(Query(question="invalid", params={}))

    def test_handle_event_returns_empty(self) -> None:
        from dnd_simulator.core.models import Event

        layer = GeographyLayer()
        event = Event(event_type=EventType.WEATHER_CHANGED, source_layer="test")
        assert layer.handle_event(event) == []


class TestGeographySaveLoad:
    def test_round_trip(self) -> None:
        """Save and load should preserve all region data."""
        original = GeographyLayer(regions=_make_test_regions(), weather_seed=42)

        # Modify some state
        state_ws = WorldState(time=GameDateTime(year=1490, month=7, day=15, hour=12))
        original.tick(TimeDelta.from_hours(6), state_ws)

        # Save
        saved = original.get_state()

        # Load into new layer
        restored = GeographyLayer(weather_seed=42)
        restored.load_state(saved)

        # Compare regions
        for rid in ("forest_vale", "mountain_pass"):
            orig = original.get_region(rid)
            rest = restored.get_region(rid)
            assert orig.id == rest.id
            assert orig.name == rest.name
            assert orig.latitude == rest.latitude
            assert orig.longitude == rest.longitude
            assert orig.elevation == rest.elevation
            assert orig.terrain == rest.terrain
            assert orig.water_proximity == rest.water_proximity
            assert orig.weather == rest.weather
            assert orig.temperature == rest.temperature
            assert len(orig.connections) == len(rest.connections)

    def test_load_empty_state(self) -> None:
        layer = GeographyLayer()
        layer.load_state({"regions": {}})
        answer = layer.query(Query(question="regions", params={}))
        assert answer.value == []
