"""Economy subsystem — income, trade, upkeep."""

from __future__ import annotations

from collections.abc import Callable

from dnd_simulator.layers.politics.models import DiplomaticStatus, LeaderTrait, Nation
from dnd_simulator.rules.politics import (
    calculate_military_upkeep,
    calculate_region_income,
    calculate_trade_income,
    clamp,
)

MERCHANT_INCOME_MULTIPLIER = 1.3


def _count_trade_partners(
    nation_id: str,
    relations: dict[tuple[str, str], DiplomaticStatus],
) -> int:
    """Count nations with trade agreement or alliance."""
    count = 0
    for key, status in relations.items():
        if nation_id in key and status in (DiplomaticStatus.TRADE_AGREEMENT, DiplomaticStatus.ALLIANCE):
            count += 1
    return count


def process_economy(
    nations: dict[str, Nation],
    relations: dict[tuple[str, str], DiplomaticStatus],
    region_terrains: dict[str, str],
    *,
    region_income_fn: Callable[[str], float] | None = None,
) -> None:
    """Calculate income, trade, and upkeep for each nation. Mutates nations in place."""
    for nation in nations.values():
        # Base income from controlled regions
        if region_income_fn:
            income = sum(region_income_fn(rid) for rid in nation.regions)
        else:
            income = sum(calculate_region_income(region_terrains.get(rid, "plains")) for rid in nation.regions)

        # Trade income
        trade_partners = _count_trade_partners(nation.id, relations)
        income += calculate_trade_income(nation.wealth, trade_partners)

        # Leader merchant bonus
        if nation.leader and nation.leader.trait == LeaderTrait.MERCHANT:
            income *= MERCHANT_INCOME_MULTIPLIER

        # Military upkeep
        upkeep = calculate_military_upkeep(nation.military)

        nation.wealth = clamp(nation.wealth + income - upkeep)
