"""Data models for the geography layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dnd_simulator.core.models import Season, TerrainType, WeatherCondition

# Re-export so existing `from .models import ...` still works
__all__ = ["Connection", "Direction", "Region", "Season", "TerrainType", "WeatherCondition"]


class Direction(Enum):
    """Compass directions for region connections."""

    N = "n"
    NE = "ne"
    E = "e"
    SE = "se"
    S = "s"
    SW = "sw"
    W = "w"
    NW = "nw"


@dataclass(frozen=True)
class Connection:
    """A link between two regions."""

    target_id: str
    direction: Direction


@dataclass
class Region:
    """A geographic area in the world."""

    id: str
    name: str
    latitude: float  # -90 to 90, positive = north
    longitude: float  # -180 to 180
    elevation: float  # meters above sea level
    terrain: TerrainType
    water_proximity: float  # 0.0 (landlocked) to 1.0 (coastal/island)
    connections: list[Connection] = field(default_factory=list)
    weather: WeatherCondition = WeatherCondition.CLEAR
    temperature: float = 15.0  # Celsius, recalculated on tick
