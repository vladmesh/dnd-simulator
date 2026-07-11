"""Persisted creature intentions that span game time."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dnd_simulator.core.resource import RestType


class IntentType(StrEnum):
    """Kinds of timed intent supported by the current simulation."""

    WAIT = "wait"
    SLEEP = "sleep"
    TRAVEL = "travel"


@dataclass(frozen=True)
class TimedIntent:
    """A creature activity with an absolute start and wake boundary."""

    kind: IntentType
    started_at_seconds: int
    wake_at_seconds: int
    rest_type: RestType | None = None

    def __post_init__(self) -> None:
        if self.kind not in (IntentType.WAIT, IntentType.SLEEP):
            raise ValueError("timed intent must be wait or sleep")
        if self.wake_at_seconds < self.started_at_seconds:
            raise ValueError("wake time cannot precede intent start time")
        if self.rest_type is not None and self.kind is not IntentType.SLEEP:
            raise ValueError("rest completion requires a sleep intent")


@dataclass(frozen=True)
class TravelIntent:
    """A persisted multi-leg journey waiting for its next edge arrival."""

    started_at_seconds: int
    destination_id: str
    remaining_route: tuple[str, ...]
    next_arrival_seconds: int
    kind: IntentType = IntentType.TRAVEL

    def __post_init__(self) -> None:
        if self.kind is not IntentType.TRAVEL:
            raise ValueError("travel intent must use the travel kind")
        if not self.remaining_route:
            raise ValueError("travel route cannot be empty")
        if self.remaining_route[-1] != self.destination_id:
            raise ValueError("travel destination must be the final route node")
        if self.next_arrival_seconds < self.started_at_seconds:
            raise ValueError("arrival time cannot precede journey start time")


CreatureIntent = TimedIntent | TravelIntent
