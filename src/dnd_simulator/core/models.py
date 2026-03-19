from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(Enum):
    """Types of events that can flow between layers."""

    ENTITY_DIED = "entity_died"
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

    def advance(self, hours: int = 0, days: int = 0) -> GameDateTime:
        total_minutes = self.minute
        total_hours = self.hour + hours
        total_days = self.day + days

        total_hours += total_minutes // 60
        total_days += total_hours // 24
        hour = total_hours % 24

        # Simplified: 30 days per month, 12 months per year
        month = self.month + (total_days - 1) // 30
        day = (total_days - 1) % 30 + 1
        year = self.year + (month - 1) // 12
        month = (month - 1) % 12 + 1

        return GameDateTime(year=year, month=month, day=day, hour=hour, minute=self.minute)


@dataclass(frozen=True)
class TimeDelta:
    """Duration of time in game."""

    hours: int = 0
    days: int = 0

    @property
    def total_hours(self) -> int:
        return self.days * 24 + self.hours


@dataclass(frozen=True)
class Event:
    """An event that occurred in the world."""

    event_type: EventType
    source_layer: str
    data: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True)
class Query:
    """A question to a specific layer."""

    question: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Answer:
    """Response from a layer to a query."""

    value: Any
    description: str = ""
