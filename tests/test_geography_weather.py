"""Tests for the weather engine Markov chain."""

from dnd_simulator.layers.geography.models import (
    Region,
    Season,
    TerrainType,
    WeatherCondition,
)
from dnd_simulator.layers.geography.weather import WeatherEngine


def _make_region(
    terrain: TerrainType = TerrainType.PLAINS,
    weather: WeatherCondition = WeatherCondition.CLEAR,
    water_proximity: float = 0.0,
    latitude: float = 45.0,
) -> Region:
    return Region(
        id="test",
        name="Test Region",
        latitude=latitude,
        longitude=0.0,
        elevation=0.0,
        terrain=terrain,
        water_proximity=water_proximity,
        weather=weather,
    )


class TestWeatherEngine:
    def test_deterministic_with_seed(self) -> None:
        """Same seed produces same weather sequence."""
        region1 = _make_region()
        region2 = _make_region()

        engine1 = WeatherEngine(seed=42)
        engine2 = WeatherEngine(seed=42)

        results1 = [engine1.next_weather(region1, Season.SUMMER, 20.0) for _ in range(10)]
        results2 = [engine2.next_weather(region2, Season.SUMMER, 20.0) for _ in range(10)]

        assert results1 == results2

    def test_returns_valid_weather(self) -> None:
        engine = WeatherEngine(seed=1)
        region = _make_region()

        for _ in range(50):
            result = engine.next_weather(region, Season.SUMMER, 20.0)
            assert isinstance(result, WeatherCondition)
            region.weather = result

    def test_no_snow_when_warm(self) -> None:
        """At high temperatures, snow should convert to rain."""
        region = _make_region(weather=WeatherCondition.CLOUDY)

        results = set()
        for i in range(200):
            engine_i = WeatherEngine(seed=i)
            result = engine_i.next_weather(region, Season.SUMMER, 25.0)
            results.add(result)

        assert WeatherCondition.SNOW not in results
        assert WeatherCondition.BLIZZARD not in results

    def test_no_rain_when_freezing(self) -> None:
        """At very cold temperatures, rain should convert to snow."""
        region = _make_region(weather=WeatherCondition.CLOUDY)

        results = set()
        for i in range(200):
            engine_i = WeatherEngine(seed=i)
            result = engine_i.next_weather(region, Season.WINTER, -15.0)
            results.add(result)

        assert WeatherCondition.LIGHT_RAIN not in results
        assert WeatherCondition.HEAVY_RAIN not in results
        assert WeatherCondition.STORM not in results

    def test_desert_favors_clear(self) -> None:
        """Desert terrain should produce more clear weather."""
        clear_count = 0
        total = 500

        for i in range(total):
            engine = WeatherEngine(seed=i)
            region = _make_region(terrain=TerrainType.DESERT)
            result = engine.next_weather(region, Season.SUMMER, 35.0)
            if result == WeatherCondition.CLEAR:
                clear_count += 1

        # Desert starting from CLEAR should stay clear most of the time
        assert clear_count / total > 0.5
