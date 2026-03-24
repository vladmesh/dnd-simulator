"""Tests for politics calculation formulas."""

from dnd_simulator.rules.politics import (
    calculate_military_upkeep,
    calculate_region_income,
    calculate_stability_drift,
    calculate_trade_income,
    calculate_war_strength,
    clamp,
    leader_death_chance,
    peace_chance,
    rebellion_chance,
    war_declaration_chance,
)


class TestRegionIncome:
    def test_coast_highest(self) -> None:
        assert calculate_region_income("coast") > calculate_region_income("plains")

    def test_tundra_lowest(self) -> None:
        assert calculate_region_income("tundra") < calculate_region_income("desert")

    def test_unknown_terrain_default(self) -> None:
        assert calculate_region_income("volcano") == 1.0


class TestTradeIncome:
    def test_no_partners_no_income(self) -> None:
        assert calculate_trade_income(50.0, 0) == 0.0

    def test_more_partners_more_income(self) -> None:
        one = calculate_trade_income(50.0, 1)
        three = calculate_trade_income(50.0, 3)
        assert three > one

    def test_diminishing_returns(self) -> None:
        two = calculate_trade_income(50.0, 2)
        one = calculate_trade_income(50.0, 1)
        # Second partner gives less than first
        marginal_second = two - one
        assert marginal_second < one

    def test_more_wealth_more_trade(self) -> None:
        poor = calculate_trade_income(20.0, 1)
        rich = calculate_trade_income(80.0, 1)
        assert rich > poor


class TestMilitaryUpkeep:
    def test_small_army_cheap(self) -> None:
        assert calculate_military_upkeep(10.0) < 1.0

    def test_large_army_expensive(self) -> None:
        assert calculate_military_upkeep(80.0) > 15.0

    def test_quadratic_scaling(self) -> None:
        small = calculate_military_upkeep(20.0)
        large = calculate_military_upkeep(40.0)
        # Doubling military should roughly 4x the cost
        assert large / small > 3.0


class TestWarStrength:
    def test_stronger_military_wins(self) -> None:
        strong = calculate_war_strength(80.0, 70.0, 0.5)
        weak = calculate_war_strength(30.0, 70.0, 0.5)
        assert strong > weak

    def test_stability_matters(self) -> None:
        stable = calculate_war_strength(50.0, 90.0, 0.5)
        unstable = calculate_war_strength(50.0, 30.0, 0.5)
        assert stable > unstable

    def test_lucky_roll_helps(self) -> None:
        lucky = calculate_war_strength(50.0, 50.0, 1.0)
        unlucky = calculate_war_strength(50.0, 50.0, 0.0)
        assert lucky > unlucky


class TestStabilityDrift:
    def test_war_destabilizes(self) -> None:
        peace_drift = calculate_stability_drift(50.0, False, 50.0, None)
        war_drift = calculate_stability_drift(50.0, True, 50.0, None)
        assert war_drift < peace_drift

    def test_poverty_destabilizes(self) -> None:
        rich = calculate_stability_drift(50.0, False, 80.0, None)
        poor = calculate_stability_drift(50.0, False, 10.0, None)
        assert rich > poor

    def test_diplomat_stabilizes(self) -> None:
        normal = calculate_stability_drift(50.0, False, 50.0, None)
        diplomat = calculate_stability_drift(50.0, False, 50.0, "diplomat")
        assert diplomat > normal

    def test_mean_reversion(self) -> None:
        high = calculate_stability_drift(90.0, False, 50.0, None)
        low = calculate_stability_drift(10.0, False, 50.0, None)
        assert low > high  # low stability drifts up, high drifts down


class TestLeaderDeathChance:
    def test_young_leader_immortal(self) -> None:
        assert leader_death_chance(30) == 0.0

    def test_old_leader_mortal(self) -> None:
        assert leader_death_chance(70) > 0.05

    def test_increases_with_age(self) -> None:
        assert leader_death_chance(60) < leader_death_chance(80)


class TestRebellionChance:
    def test_stable_nation_no_rebellion(self) -> None:
        assert rebellion_chance(50.0) == 0.0

    def test_unstable_nation_rebellion(self) -> None:
        assert rebellion_chance(5.0) > 0.0

    def test_threshold_at_20(self) -> None:
        assert rebellion_chance(20.0) == 0.0
        assert rebellion_chance(19.0) > 0.0


class TestWarDeclarationChance:
    def test_weaker_never_attacks(self) -> None:
        assert war_declaration_chance(30.0, 50.0, None) == 0.0

    def test_stronger_may_attack(self) -> None:
        assert war_declaration_chance(80.0, 30.0, None) > 0.0

    def test_militarist_more_aggressive(self) -> None:
        normal = war_declaration_chance(70.0, 40.0, None)
        militarist = war_declaration_chance(70.0, 40.0, "militarist")
        assert militarist > normal

    def test_diplomat_less_aggressive(self) -> None:
        normal = war_declaration_chance(70.0, 40.0, None)
        diplomat = war_declaration_chance(70.0, 40.0, "diplomat")
        assert diplomat < normal


class TestPeaceChance:
    def test_increases_with_time(self) -> None:
        early = peace_chance(1)
        late = peace_chance(10)
        assert late > early

    def test_capped(self) -> None:
        assert peace_chance(100) <= 0.3


class TestClamp:
    def test_within_range(self) -> None:
        assert clamp(50.0) == 50.0

    def test_below_min(self) -> None:
        assert clamp(-10.0) == 0.0

    def test_above_max(self) -> None:
        assert clamp(120.0) == 100.0
