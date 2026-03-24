"""Tests for settlement formulas."""

from dnd_simulator.rules.settlements import (
    calculate_harvest_modifier,
    calculate_population_change,
    calculate_settlement_income,
    clamp,
    conquest_effects,
    prosperity_drift,
)


class TestSettlementIncome:
    def test_city_coast_high_prosperity(self) -> None:
        income = calculate_settlement_income("city", "coast", 100.0)
        assert income == 10.4  # 8.0 * 1.3 * 1.0

    def test_village_plains_mid_prosperity(self) -> None:
        income = calculate_settlement_income("village", "plains", 50.0)
        assert income == 0.9  # 1.5 * 1.2 * 0.5

    def test_town_tundra_low_prosperity(self) -> None:
        income = calculate_settlement_income("town", "tundra", 20.0)
        assert income == 0.4  # 4.0 * 0.5 * 0.2

    def test_zero_prosperity_no_income(self) -> None:
        assert calculate_settlement_income("city", "coast", 0.0) == 0.0


class TestHarvestModifier:
    def test_clear_weather_village(self) -> None:
        mod = calculate_harvest_modifier("clear", "village")
        assert mod == 3.0  # 2.0 * 1.5

    def test_clear_weather_city(self) -> None:
        mod = calculate_harvest_modifier("clear", "city")
        assert mod == 0.6  # 2.0 * 0.3

    def test_blizzard_village(self) -> None:
        mod = calculate_harvest_modifier("blizzard", "village")
        assert mod == -7.5  # -5.0 * 1.5

    def test_light_rain_good_for_crops(self) -> None:
        mod = calculate_harvest_modifier("light_rain", "village")
        assert mod > 0

    def test_fog_neutral(self) -> None:
        assert calculate_harvest_modifier("fog", "town") == 0.0


class TestPopulationChange:
    def test_high_prosperity_growth(self) -> None:
        change = calculate_population_change(1000, 70.0)
        assert change == 20  # 2% of 1000

    def test_mid_prosperity_small_growth(self) -> None:
        change = calculate_population_change(1000, 50.0)
        assert change == 5  # 0.5% of 1000

    def test_low_prosperity_decline(self) -> None:
        change = calculate_population_change(1000, 30.0)
        assert change == -10  # -1% of 1000

    def test_very_low_prosperity_fast_decline(self) -> None:
        change = calculate_population_change(1000, 10.0)
        assert change == -20  # -2% of 1000


class TestConquestEffects:
    def test_village_effects(self) -> None:
        pros, defs, pop = conquest_effects("village")
        assert pros == -20.0
        assert defs == -15.0
        assert pop == 0.10

    def test_city_more_disruption(self) -> None:
        pros, defs, pop = conquest_effects("city")
        assert pros == -25.0
        assert defs == -25.0
        assert pop == 0.05

    def test_town_effects(self) -> None:
        pros, _defs, _pop = conquest_effects("town")
        assert pros == -15.0


class TestProsperityDrift:
    def test_wealthy_stable_nation(self) -> None:
        drift = prosperity_drift(50.0, 70.0, 70.0)
        assert drift > 0  # should increase

    def test_poor_nation(self) -> None:
        drift = prosperity_drift(50.0, 20.0, 70.0)
        assert drift < 0  # should decrease

    def test_unstable_nation(self) -> None:
        drift = prosperity_drift(50.0, 50.0, 20.0)
        assert drift < 0

    def test_mean_reversion(self) -> None:
        high = prosperity_drift(90.0, 50.0, 50.0)
        low = prosperity_drift(10.0, 50.0, 50.0)
        assert high < low  # high prosperity drifts down, low drifts up


class TestClamp:
    def test_within_range(self) -> None:
        assert clamp(50.0) == 50.0

    def test_below_min(self) -> None:
        assert clamp(-10.0) == 0.0

    def test_above_max(self) -> None:
        assert clamp(120.0) == 100.0
