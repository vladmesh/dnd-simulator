"""Geography layer — the physical world.

Simulates the aspects of reality that exist independent of civilization:
- Regions with coordinates (latitude/longitude), elevation, terrain types
- Weather via Markov chains with modifiers (season, terrain, altitude, water proximity)
- Temperature from formulas (latitude + elevation + season + time of day)
- Day/night cycle and daylight duration from latitude and time of year

This is the lowest simulation layer. It has no dependencies on other layers.
"""

from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import (
    Connection,
    Direction,
    Region,
    Season,
    TerrainType,
    WeatherCondition,
)

__all__ = [
    "Connection",
    "Direction",
    "GeographyLayer",
    "Region",
    "Season",
    "TerrainType",
    "WeatherCondition",
]
