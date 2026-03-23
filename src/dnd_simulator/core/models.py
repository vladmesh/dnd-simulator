from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TerrainType(Enum):
    """Types of terrain a region can have."""

    PLAINS = "plains"
    FOREST = "forest"
    HILLS = "hills"
    MOUNTAINS = "mountains"
    DESERT = "desert"
    SWAMP = "swamp"
    COAST = "coast"
    TUNDRA = "tundra"


class WeatherCondition(Enum):
    """Possible weather states."""

    CLEAR = "clear"
    CLOUDY = "cloudy"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    STORM = "storm"
    SNOW = "snow"
    BLIZZARD = "blizzard"
    FOG = "fog"


class Season(Enum):
    """Seasons of the year."""

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class EventType(Enum):
    """Types of events that can flow between layers."""

    ENTITY_DIED = "entity_died"
    ENTITY_SAY = "entity_say"
    ENTITY_ATTACK = "entity_attack"
    ENTITY_DODGE = "entity_dodge"
    ENTITY_FLEE = "entity_flee"
    ENTITY_MOVE = "entity_move"
    ENTITY_DASH = "entity_dash"
    ENTITY_USE_ITEM = "entity_use_item"
    TURN_SKIPPED = "turn_skipped"
    COMBAT_STARTED = "combat_started"
    COMBAT_ENDED = "combat_ended"
    WEATHER_CHANGED = "weather_changed"
    TIME_ADVANCED = "time_advanced"
    CUSTOM = "custom"


@dataclass(frozen=True)
class GameDateTime:
    """In-game date and time."""

    year: int = 1
    month: int = 1
    day: int = 1
    hour: int = 0
    minute: int = 0
    second: int = 0

    def advance(self, hours: int = 0, days: int = 0, seconds: int = 0) -> GameDateTime:
        total_seconds = self.second + seconds
        total_minutes = self.minute + total_seconds // 60
        second = total_seconds % 60

        total_hours = self.hour + hours + total_minutes // 60
        minute = total_minutes % 60

        total_days = self.day + days + total_hours // 24
        hour = total_hours % 24

        # Simplified: 30 days per month, 12 months per year
        month = self.month + (total_days - 1) // 30
        day = (total_days - 1) % 30 + 1
        year = self.year + (month - 1) // 12
        month = (month - 1) % 12 + 1

        return GameDateTime(year=year, month=month, day=day, hour=hour, minute=minute, second=second)

    def to_total_seconds(self) -> int:
        """Convert to absolute seconds since epoch (year 1, month 1, day 1)."""
        return (
            ((self.year - 1) * 12 + (self.month - 1)) * 30 * 86400
            + (self.day - 1) * 86400
            + self.hour * 3600
            + self.minute * 60
            + self.second
        )


@dataclass(frozen=True)
class TimeDelta:
    """Duration of time in game, measured in seconds."""

    seconds: int = 0

    @property
    def rounds(self) -> int:
        """Number of complete D&D rounds (6 seconds each)."""
        return self.seconds // 6

    @property
    def total_hours(self) -> int:
        """Number of complete hours."""
        return self.seconds // 3600

    @classmethod
    def from_rounds(cls, rounds: int) -> TimeDelta:
        return cls(seconds=rounds * 6)

    @classmethod
    def from_hours(cls, hours: int) -> TimeDelta:
        return cls(seconds=hours * 3600)

    @classmethod
    def from_days(cls, days: int) -> TimeDelta:
        return cls(seconds=days * 86400)


@dataclass(frozen=True)
class Event:
    """An event that occurred in the world."""

    event_type: EventType
    source_layer: str
    data: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    observer_ids: frozenset[str] | None = None  # None = public (all in area see it)


@dataclass(frozen=True)
class ActionResult:
    """Outcome of an action submitted to the world.

    success=True means the action was executed (even if attack missed).
    success=False means it was rejected (invalid target, wrong region, etc.)
    and the actor should try something else.
    """

    success: bool = True
    error: str = ""
    events: list[Event] = field(default_factory=list)


@dataclass(frozen=True)
class Query:
    """A question to a specific layer."""

    question: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Answer:
    """Response from a layer to a query."""

    value: Any
    description: str = ""


# Callback types for layer isolation — layers receive these instead of World
QueryFn = Callable[[str, Query], Answer]
"""Query another layer: (target_layer_name, query) -> answer. Only layers below the caller."""

EmitFn = Callable[[Event], ActionResult]
"""Emit an event into the world: (event) -> action_result."""
