"""Markov chain weather simulation.

Weather transitions are based on a probability matrix modified by
terrain, season, and temperature. When temperature is above 2C,
snow converts to rain; below -2C, rain converts to snow.
"""

from __future__ import annotations

import random

from dnd_simulator.layers.geography.models import (
    Region,
    Season,
    TerrainType,
    WeatherCondition,
)

# Base transition probabilities: current_state -> {next_state: probability}
_BASE_TRANSITIONS: dict[WeatherCondition, dict[WeatherCondition, float]] = {
    WeatherCondition.CLEAR: {
        WeatherCondition.CLEAR: 0.60,
        WeatherCondition.CLOUDY: 0.30,
        WeatherCondition.FOG: 0.10,
    },
    WeatherCondition.CLOUDY: {
        WeatherCondition.CLEAR: 0.30,
        WeatherCondition.CLOUDY: 0.30,
        WeatherCondition.LIGHT_RAIN: 0.20,
        WeatherCondition.FOG: 0.10,
        WeatherCondition.SNOW: 0.10,
    },
    WeatherCondition.LIGHT_RAIN: {
        WeatherCondition.CLEAR: 0.10,
        WeatherCondition.CLOUDY: 0.30,
        WeatherCondition.LIGHT_RAIN: 0.30,
        WeatherCondition.HEAVY_RAIN: 0.20,
        WeatherCondition.FOG: 0.10,
    },
    WeatherCondition.HEAVY_RAIN: {
        WeatherCondition.CLOUDY: 0.20,
        WeatherCondition.LIGHT_RAIN: 0.30,
        WeatherCondition.HEAVY_RAIN: 0.30,
        WeatherCondition.STORM: 0.20,
    },
    WeatherCondition.STORM: {
        WeatherCondition.CLEAR: 0.10,
        WeatherCondition.CLOUDY: 0.20,
        WeatherCondition.HEAVY_RAIN: 0.40,
        WeatherCondition.STORM: 0.30,
    },
    WeatherCondition.SNOW: {
        WeatherCondition.CLEAR: 0.15,
        WeatherCondition.CLOUDY: 0.25,
        WeatherCondition.SNOW: 0.40,
        WeatherCondition.BLIZZARD: 0.10,
        WeatherCondition.FOG: 0.10,
    },
    WeatherCondition.BLIZZARD: {
        WeatherCondition.CLOUDY: 0.20,
        WeatherCondition.SNOW: 0.50,
        WeatherCondition.BLIZZARD: 0.30,
    },
    WeatherCondition.FOG: {
        WeatherCondition.CLEAR: 0.40,
        WeatherCondition.CLOUDY: 0.30,
        WeatherCondition.FOG: 0.20,
        WeatherCondition.LIGHT_RAIN: 0.10,
    },
}


def _normalize(
    probs: dict[WeatherCondition, float],
) -> dict[WeatherCondition, float]:
    """Normalize probabilities to sum to 1.0."""
    total = sum(probs.values())
    if total == 0:
        return {WeatherCondition.CLEAR: 1.0}
    return {k: v / total for k, v in probs.items()}


def _apply_terrain_modifiers(
    probs: dict[WeatherCondition, float],
    terrain: TerrainType,
    water_proximity: float,
) -> dict[WeatherCondition, float]:
    """Modify transition probabilities based on terrain and water."""
    result = dict(probs)

    if terrain == TerrainType.DESERT:
        result[WeatherCondition.CLEAR] = result.get(WeatherCondition.CLEAR, 0) * 2.0
        for wet in (
            WeatherCondition.LIGHT_RAIN,
            WeatherCondition.HEAVY_RAIN,
            WeatherCondition.STORM,
        ):
            result[wet] = result.get(wet, 0) * 0.2
        result[WeatherCondition.SNOW] = result.get(WeatherCondition.SNOW, 0) * 0.1
        result[WeatherCondition.BLIZZARD] = 0.0

    elif terrain == TerrainType.MOUNTAINS:
        result[WeatherCondition.STORM] = result.get(WeatherCondition.STORM, 0) * 1.5
        result[WeatherCondition.SNOW] = result.get(WeatherCondition.SNOW, 0) * 1.5
        result[WeatherCondition.BLIZZARD] = result.get(WeatherCondition.BLIZZARD, 0) * 1.3

    elif terrain == TerrainType.SWAMP:
        result[WeatherCondition.FOG] = result.get(WeatherCondition.FOG, 0) * 2.0
        result[WeatherCondition.LIGHT_RAIN] = result.get(WeatherCondition.LIGHT_RAIN, 0) * 1.5

    elif terrain == TerrainType.FOREST:
        result[WeatherCondition.FOG] = result.get(WeatherCondition.FOG, 0) * 1.3

    # Water proximity increases rain and fog
    if water_proximity > 0.5:
        factor = 1.0 + water_proximity
        result[WeatherCondition.LIGHT_RAIN] = result.get(WeatherCondition.LIGHT_RAIN, 0) * factor
        result[WeatherCondition.FOG] = result.get(WeatherCondition.FOG, 0) * factor

    return result


def _apply_season_modifiers(
    probs: dict[WeatherCondition, float],
    season: Season,
) -> dict[WeatherCondition, float]:
    """Modify transition probabilities based on season."""
    result = dict(probs)

    if season == Season.WINTER:
        result[WeatherCondition.SNOW] = result.get(WeatherCondition.SNOW, 0) * 2.0
        result[WeatherCondition.BLIZZARD] = result.get(WeatherCondition.BLIZZARD, 0) * 2.0
        result[WeatherCondition.CLEAR] = result.get(WeatherCondition.CLEAR, 0) * 0.7

    elif season == Season.SUMMER:
        result[WeatherCondition.SNOW] = result.get(WeatherCondition.SNOW, 0) * 0.1
        result[WeatherCondition.BLIZZARD] = 0.0
        result[WeatherCondition.CLEAR] = result.get(WeatherCondition.CLEAR, 0) * 1.5
        result[WeatherCondition.STORM] = result.get(WeatherCondition.STORM, 0) * 1.3

    elif season == Season.SPRING:
        result[WeatherCondition.LIGHT_RAIN] = result.get(WeatherCondition.LIGHT_RAIN, 0) * 1.3
        result[WeatherCondition.FOG] = result.get(WeatherCondition.FOG, 0) * 1.2

    elif season == Season.AUTUMN:
        result[WeatherCondition.LIGHT_RAIN] = result.get(WeatherCondition.LIGHT_RAIN, 0) * 1.4
        result[WeatherCondition.FOG] = result.get(WeatherCondition.FOG, 0) * 1.3
        result[WeatherCondition.CLOUDY] = result.get(WeatherCondition.CLOUDY, 0) * 1.2

    return result


def _apply_temperature_conversion(
    probs: dict[WeatherCondition, float],
    base_temperature: float,
) -> dict[WeatherCondition, float]:
    """Convert rain<->snow based on temperature."""
    result = dict(probs)

    if base_temperature > 2.0:
        # Too warm for snow -> convert to rain
        snow = result.get(WeatherCondition.SNOW, 0)
        blizzard = result.get(WeatherCondition.BLIZZARD, 0)
        result[WeatherCondition.LIGHT_RAIN] = result.get(WeatherCondition.LIGHT_RAIN, 0) + snow
        result[WeatherCondition.HEAVY_RAIN] = result.get(WeatherCondition.HEAVY_RAIN, 0) + blizzard
        result[WeatherCondition.SNOW] = 0.0
        result[WeatherCondition.BLIZZARD] = 0.0

    elif base_temperature < -2.0:
        # Too cold for rain -> convert to snow
        light = result.get(WeatherCondition.LIGHT_RAIN, 0)
        heavy = result.get(WeatherCondition.HEAVY_RAIN, 0)
        storm = result.get(WeatherCondition.STORM, 0)
        result[WeatherCondition.SNOW] = result.get(WeatherCondition.SNOW, 0) + light + heavy
        result[WeatherCondition.BLIZZARD] = result.get(WeatherCondition.BLIZZARD, 0) + storm
        result[WeatherCondition.LIGHT_RAIN] = 0.0
        result[WeatherCondition.HEAVY_RAIN] = 0.0
        result[WeatherCondition.STORM] = 0.0

    return result


class WeatherEngine:
    """Markov chain weather simulation with terrain/season/temperature modifiers."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def next_weather(
        self,
        region: Region,
        season: Season,
        base_temperature: float,
    ) -> WeatherCondition:
        """Determine next weather condition for a region."""
        probs = dict(_BASE_TRANSITIONS.get(region.weather, {WeatherCondition.CLEAR: 1.0}))

        probs = _apply_terrain_modifiers(probs, region.terrain, region.water_proximity)
        probs = _apply_season_modifiers(probs, season)
        probs = _apply_temperature_conversion(probs, base_temperature)
        probs = _normalize(probs)

        conditions = list(probs.keys())
        weights = [probs[c] for c in conditions]
        return self._rng.choices(conditions, weights=weights, k=1)[0]
