"""Pure functions for politics calculations.

Stateless formulas for economy, warfare, stability, and diplomacy.
Uses primitive types to stay decoupled from other layers.
"""

from __future__ import annotations

import math

# Base monthly income per terrain type (gold/month).
_TERRAIN_INCOME: dict[str, float] = {
    "plains": 3.0,
    "coast": 4.0,
    "forest": 2.0,
    "hills": 2.0,
    "mountains": 1.5,
    "desert": 1.0,
    "swamp": 1.0,
    "tundra": 0.5,
}


def calculate_region_income(terrain: str) -> float:
    """Base monthly income from a region based on terrain."""
    return _TERRAIN_INCOME.get(terrain, 1.0)


def calculate_trade_income(wealth: float, num_trade_partners: int) -> float:
    """Income from trade agreements. Diminishing returns per partner."""
    if num_trade_partners <= 0:
        return 0.0
    base = wealth * 0.02
    return round(base * math.sqrt(num_trade_partners), 1)


def calculate_military_upkeep(military: float) -> float:
    """Cost of maintaining military. Quadratic scaling — big armies are expensive."""
    return round(military * military * 0.003, 1)


def calculate_war_strength(military: float, stability: float, dice: float) -> float:
    """Effective combat strength. dice is 0.0-1.0 random value."""
    return military * (stability / 100.0) * (0.5 + dice)


def calculate_stability_drift(
    stability: float,
    at_war: bool,
    wealth: float,
    leader_trait: str | None,
) -> float:
    """Monthly stability change. Positive = stabilizing, negative = destabilizing."""
    drift = 0.0

    if at_war:
        drift -= 2.0

    if wealth < 20:
        drift -= 2.0
    elif wealth < 40:
        drift -= 1.0
    elif wealth > 70:
        drift += 1.0

    # Mean reversion toward 50
    drift += (50.0 - stability) * 0.05

    if leader_trait == "diplomat":
        drift += 1.5

    return round(drift, 1)


def leader_death_chance(age: int) -> float:
    """Monthly probability of leader dying. Rises sharply after 40."""
    if age < 40:
        return 0.0
    return float(min(0.5, 0.001 * (age - 35) ** 1.5))


def rebellion_chance(stability: float) -> float:
    """Monthly probability of rebellion when stability is critically low."""
    if stability >= 20:
        return 0.0
    return (20.0 - stability) / 100.0 * 0.75


def war_declaration_chance(
    nation_military: float,
    target_military: float,
    leader_trait: str | None,
) -> float:
    """Monthly probability of declaring war on a neighbor."""
    if nation_military <= target_military:
        return 0.0

    ratio = nation_military / max(target_military, 1.0)
    base = min(0.05, (ratio - 1.0) * 0.02)

    if leader_trait == "militarist":
        base *= 2.0
    elif leader_trait == "diplomat":
        base *= 0.3

    return round(base, 4)


def peace_chance(months_at_war: int) -> float:
    """Monthly probability of making peace. Grows with war weariness."""
    base = 0.02 + months_at_war * 0.02
    return min(0.3, round(base, 2))


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp value to range."""
    return max(low, min(high, value))
