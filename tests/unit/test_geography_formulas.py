"""Tests for geography calculation formulas."""

from dnd_simulator.layers.geography.models import Season, TerrainType, WeatherCondition
from dnd_simulator.rules.geography import (
    apply_weather_temperature_modifier,
    calculate_base_temperature,
    calculate_daylight_hours,
    calculate_distance_km,
    calculate_travel_hours,
    get_season,
    is_daylight,
)


class TestGetSeason:
    def test_northern_hemisphere_winter(self) -> None:
        assert get_season(1, 50.0) == Season.WINTER
        assert get_season(12, 50.0) == Season.WINTER

    def test_northern_hemisphere_summer(self) -> None:
        assert get_season(7, 50.0) == Season.SUMMER

    def test_southern_hemisphere_inverted(self) -> None:
        # July in southern hemisphere is winter
        assert get_season(7, -30.0) == Season.WINTER
        # January in southern hemisphere is summer
        assert get_season(1, -30.0) == Season.SUMMER

    def test_equator_still_has_seasons(self) -> None:
        # Latitude 0 is technically northern hemisphere
        assert get_season(7, 0.0) == Season.SUMMER


class TestCalculateBaseTemperature:
    def test_equator_warmer_than_poles(self) -> None:
        equator = calculate_base_temperature(0.0, 7, 12, 0.0)
        arctic = calculate_base_temperature(70.0, 7, 12, 0.0)
        assert equator > arctic

    def test_elevation_cools(self) -> None:
        sea_level = calculate_base_temperature(45.0, 7, 12, 0.0)
        mountain = calculate_base_temperature(45.0, 7, 12, 3000.0)
        # 3000m should be ~19.5C cooler
        assert sea_level - mountain > 15.0

    def test_afternoon_warmer_than_dawn(self) -> None:
        dawn = calculate_base_temperature(45.0, 7, 5, 0.0)
        afternoon = calculate_base_temperature(45.0, 7, 15, 0.0)
        assert afternoon > dawn

    def test_summer_warmer_than_winter(self) -> None:
        summer = calculate_base_temperature(45.0, 7, 12, 0.0)
        winter = calculate_base_temperature(45.0, 1, 12, 0.0)
        assert summer > winter


class TestWeatherTemperatureModifier:
    def test_clear_no_change(self) -> None:
        assert apply_weather_temperature_modifier(20.0, WeatherCondition.CLEAR) == 20.0

    def test_storm_cools(self) -> None:
        result = apply_weather_temperature_modifier(20.0, WeatherCondition.STORM)
        assert result < 20.0

    def test_blizzard_cools_most(self) -> None:
        storm = apply_weather_temperature_modifier(20.0, WeatherCondition.STORM)
        blizzard = apply_weather_temperature_modifier(20.0, WeatherCondition.BLIZZARD)
        assert blizzard < storm


class TestDaylightHours:
    def test_equator_roughly_12_hours(self) -> None:
        hours = calculate_daylight_hours(0.0, 6)
        assert 11.5 < hours < 12.5

    def test_high_latitude_summer_long_days(self) -> None:
        hours = calculate_daylight_hours(65.0, 6)
        assert hours > 20.0

    def test_high_latitude_winter_short_days(self) -> None:
        hours = calculate_daylight_hours(65.0, 12)
        assert hours < 6.0

    def test_polar_midnight_sun(self) -> None:
        hours = calculate_daylight_hours(80.0, 6)
        assert hours == 24.0

    def test_polar_night(self) -> None:
        hours = calculate_daylight_hours(80.0, 12)
        assert hours == 0.0


class TestIsDaylight:
    def test_noon_is_day(self) -> None:
        assert is_daylight(45.0, 6, 12) is True

    def test_midnight_is_night(self) -> None:
        assert is_daylight(45.0, 6, 0) is False

    def test_polar_midnight_sun(self) -> None:
        assert is_daylight(80.0, 6, 0) is True

    def test_polar_night(self) -> None:
        assert is_daylight(80.0, 12, 12) is False


class TestDistanceKm:
    def test_same_point_is_zero(self) -> None:
        assert calculate_distance_km(45.0, 10.0, 45.0, 10.0) == 0.0

    def test_known_distance(self) -> None:
        # Moscow (55.75, 37.62) to Saint Petersburg (59.93, 30.32) ~634 km
        dist = calculate_distance_km(55.75, 37.62, 59.93, 30.32)
        assert 600 < dist < 700

    def test_symmetry(self) -> None:
        d1 = calculate_distance_km(45.0, 10.0, 48.0, 10.5)
        d2 = calculate_distance_km(48.0, 10.5, 45.0, 10.0)
        assert d1 == d2


class TestTravelHours:
    def test_plains_fastest(self) -> None:
        plains = calculate_travel_hours(100.0, TerrainType.PLAINS, WeatherCondition.CLEAR)
        mountains = calculate_travel_hours(100.0, TerrainType.MOUNTAINS, WeatherCondition.CLEAR)
        assert plains < mountains

    def test_storm_slows_travel(self) -> None:
        clear = calculate_travel_hours(100.0, TerrainType.PLAINS, WeatherCondition.CLEAR)
        storm = calculate_travel_hours(100.0, TerrainType.PLAINS, WeatherCondition.STORM)
        assert storm > clear

    def test_elevation_gain_adds_time(self) -> None:
        flat = calculate_travel_hours(50.0, TerrainType.HILLS, WeatherCondition.CLEAR, elevation_diff=0.0)
        uphill = calculate_travel_hours(50.0, TerrainType.HILLS, WeatherCondition.CLEAR, elevation_diff=1000.0)
        assert uphill > flat
        # 1000m gain should add ~2 hours (Naismith's rule: 1h per 500m)
        assert uphill - flat > 1.5
