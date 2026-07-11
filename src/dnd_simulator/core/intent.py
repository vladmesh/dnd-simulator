"""Persisted creature intentions that span game time."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dnd_simulator.core.resource import RestType


class IntentType(StrEnum):
    """Kinds of timed intent supported by the current simulation."""

    WAIT = "wait"
    SLEEP = "sleep"


@dataclass(frozen=True)
class TimedIntent:
    """A creature activity with an absolute start and wake boundary."""

    kind: IntentType
    started_at_seconds: int
    wake_at_seconds: int
    rest_type: RestType | None = None

    def __post_init__(self) -> None:
        if self.wake_at_seconds < self.started_at_seconds:
            raise ValueError("wake time cannot precede intent start time")
        if self.rest_type is not None and self.kind is not IntentType.SLEEP:
            raise ValueError("rest completion requires a sleep intent")
