"""Pure functions for settlement calculations.

Stateless formulas for income, harvest, population, and conquest effects.
Uses primitive types to stay decoupled from other layers.
"""

from __future__ import annotations

# Base income per settlement type (gold/month).
_BASE_INCOME: dict[str, float] = {
    "village": 1.5,
    "town": 4.0,
    "city": 8.0,
}

# Terrain multiplier on settlement income.
_TERRAIN_MODIFIER: dict[str, float] = {
    "coast": 1.3,
    "plains": 1.2,
    "hills": 1.1,
    "forest": 1.0,
    "mountains": 1.0,
    "swamp": 0.7,
    "desert": 0.6,
    "tundra": 0.5,
}

# Weather effect on prosperity (harvest quality).
_WEATHER_EFFECT: dict[str, float] = {
    "clear": 2.0,
    "cloudy": 1.0,
    "light_rain": 1.5,  # rain is good for crops
    "heavy_rain": -1.0,
    "storm": -3.0,
    "snow": -2.0,
    "blizzard": -5.0,
    "fog": 0.0,
}

# How much each settlement type depends on weather/harvest.
_WEATHER_SENSITIVITY: dict[str, float] = {
    "village": 1.5,
    "town": 1.0,
    "city": 0.3,
}


def calculate_settlement_income(settlement_type: str, terrain: str, prosperity: float) -> float:
    """Income from a single settlement. Depends on type, terrain, and prosperity."""
    base = _BASE_INCOME.get(settlement_type, 1.0)
    terrain_mod = _TERRAIN_MODIFIER.get(terrain, 1.0)
    return round(base * terrain_mod * prosperity / 100.0, 1)


def calculate_harvest_modifier(weather: str, settlement_type: str) -> float:
    """Monthly prosperity change from weather (harvest quality).

    Villages depend heavily on weather, cities barely notice.
    """
    effect = _WEATHER_EFFECT.get(weather, 0.0)
    sensitivity = _WEATHER_SENSITIVITY.get(settlement_type, 1.0)
    return round(effect * sensitivity, 1)


def calculate_population_change(population: int, prosperity: float) -> int:
    """Monthly population growth or decline based on prosperity."""
    if prosperity > 60:
        rate = 0.02
    elif prosperity > 40:
        rate = 0.005
    elif prosperity > 20:
        rate = -0.01
    else:
        rate = -0.02
    return int(population * rate)


def conquest_effects(settlement_type: str) -> tuple[float, float, float]:
    """Damage from conquest: (prosperity_penalty, defenses_penalty, population_loss_fraction).

    Cities suffer more disruption but walls protect people.
    Villages lose more people but recover faster.
    """
    effects: dict[str, tuple[float, float, float]] = {
        "village": (-20.0, -15.0, 0.10),
        "town": (-15.0, -20.0, 0.05),
        "city": (-25.0, -25.0, 0.05),
    }
    return effects.get(settlement_type, (-20.0, -15.0, 0.10))


def prosperity_drift(
    prosperity: float,
    nation_wealth: float,
    nation_stability: float,
) -> float:
    """Monthly prosperity change from nation's economic and political state."""
    drift = 0.0

    if nation_wealth > 60:
        drift += 1.0
    elif nation_wealth < 30:
        drift -= 1.0

    if nation_stability < 30:
        drift -= 2.0
    elif nation_stability < 50:
        drift -= 0.5

    # Mean reversion toward 50
    drift += (50.0 - prosperity) * 0.03

    return round(drift, 1)


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp value to range."""
    return max(low, min(high, value))
