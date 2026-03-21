from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_simulator.core.models import (
        ActionResult,
        Answer,
        EmitFn,
        Event,
        GameDateTime,
        Query,
        QueryFn,
        TimeDelta,
    )


class Layer(ABC):
    """Abstract base for all simulation layers.

    Layers are stacked from most abstract (geography) to most concrete (NPCs).
    Each layer can query layers below it via query_fn, but never above.
    Events flow through emit_fn back to the World for propagation.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this layer."""

    @property
    @abstractmethod
    def tick_interval(self) -> int:
        """Minimum seconds between ticks. 0 means tick every advance_time call."""

    @abstractmethod
    def tick(self, delta: TimeDelta, time: GameDateTime, query_fn: QueryFn, emit_fn: EmitFn) -> list[Event]:
        """Advance simulation by delta time. Returns events that occurred."""

    @abstractmethod
    def handle_event(self, event: Event, query_fn: QueryFn, emit_fn: EmitFn) -> ActionResult:
        """Process an external event. Returns ActionResult with success/error and cascade events."""

    @abstractmethod
    def query(self, query: Query) -> Answer:
        """Answer a question about current state."""

    @abstractmethod
    def get_state(self) -> dict[str, object]:
        """Return serializable state for saving."""

    @abstractmethod
    def load_state(self, state: dict[str, object]) -> None:
        """Restore state from saved data."""
