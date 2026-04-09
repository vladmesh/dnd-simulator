"""Tests for politics economy submodule."""

from __future__ import annotations

import pytest

from dnd_simulator.layers.politics.models import (
    DiplomaticStatus,
    Leader,
    LeaderTrait,
    Nation,
)


def _make_nation(
    *,
    nation_id: str = "alpha",
    name: str = "Kingdom of Alpha",
    regions: list[str] | None = None,
    wealth: float = 50.0,
    military: float = 50.0,
    leader: Leader | None = None,
) -> Nation:
    return Nation(
        id=nation_id,
        name=name,
        regions=regions or ["region_a", "region_b"],
        wealth=wealth,
        military=military,
        leader=leader,
    )


class TestProcessEconomy:
    def test_basic_income_minus_upkeep(self) -> None:
        """Nation with 2 regions earns terrain income minus military upkeep."""
        from dnd_simulator.layers.politics.economy import process_economy
        from dnd_simulator.rules.politics import calculate_military_upkeep, calculate_region_income

        nation = _make_nation(wealth=50.0, military=10.0)
        nations = {nation.id: nation}
        relations: dict[tuple[str, str], DiplomaticStatus] = {}
        terrains = {"region_a": "coast", "region_b": "plains"}

        process_economy(nations, relations, terrains, region_income_fn=None)

        expected_income = calculate_region_income("coast") + calculate_region_income("plains")
        expected_upkeep = calculate_military_upkeep(10.0)
        assert nation.wealth == pytest.approx(50.0 + expected_income - expected_upkeep, abs=0.1)

    def test_trade_agreement_adds_income(self) -> None:
        """Nation with a trade partner earns extra trade income."""
        from dnd_simulator.layers.politics.economy import process_economy
        from dnd_simulator.rules.politics import (
            calculate_military_upkeep,
            calculate_region_income,
            calculate_trade_income,
        )

        alpha = _make_nation(wealth=60.0, military=10.0)
        beta = _make_nation(nation_id="beta", name="Beta", regions=["region_c"], wealth=40.0, military=10.0)
        nations = {alpha.id: alpha, beta.id: beta}
        relations = {("alpha", "beta"): DiplomaticStatus.TRADE_AGREEMENT}
        terrains = {"region_a": "coast", "region_b": "plains", "region_c": "hills"}

        process_economy(nations, relations, terrains, region_income_fn=None)

        # Alpha should have earned trade income (1 partner)
        base_income = calculate_region_income("coast") + calculate_region_income("plains")
        trade_income = calculate_trade_income(60.0, 1)
        upkeep = calculate_military_upkeep(10.0)
        assert alpha.wealth == pytest.approx(60.0 + base_income + trade_income - upkeep, abs=0.1)

    def test_merchant_leader_multiplier(self) -> None:
        """Merchant leader applies 1.3x multiplier to total income before upkeep subtraction."""
        from dnd_simulator.layers.politics.economy import MERCHANT_INCOME_MULTIPLIER, process_economy
        from dnd_simulator.rules.politics import calculate_military_upkeep, calculate_region_income

        merchant = Leader(name="Trader", age=40, trait=LeaderTrait.MERCHANT)
        nation = _make_nation(wealth=50.0, military=10.0, leader=merchant)
        nations = {nation.id: nation}
        relations: dict[tuple[str, str], DiplomaticStatus] = {}
        terrains = {"region_a": "coast", "region_b": "plains"}

        process_economy(nations, relations, terrains, region_income_fn=None)

        base_income = calculate_region_income("coast") + calculate_region_income("plains")
        boosted_income = base_income * MERCHANT_INCOME_MULTIPLIER
        upkeep = calculate_military_upkeep(10.0)
        assert nation.wealth == pytest.approx(50.0 + boosted_income - upkeep, abs=0.1)

    def test_custom_region_income_fn(self) -> None:
        """When region_income_fn is provided, it overrides terrain-based income."""
        from dnd_simulator.layers.politics.economy import process_economy

        nation = _make_nation(wealth=50.0, military=0.0, regions=["region_a"])
        nations = {nation.id: nation}
        relations: dict[tuple[str, str], DiplomaticStatus] = {}

        process_economy(nations, relations, {}, region_income_fn=lambda rid: 10.0)

        assert nation.wealth == pytest.approx(60.0, abs=0.1)
