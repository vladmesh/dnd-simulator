"""Tests for geography calculation formulas."""

from dnd_simulator.layers.geography.formulas import (
    apply_weather_temperature_modifier,
    calculate_base_temperature,
    calculate_daylight_hours,
    get_season,
)
from dnd_simulator.layers.geography.models import Season, WeatherCondition


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
