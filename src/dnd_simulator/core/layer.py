from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_simulator.core.models import Answer, Event, Query, TimeDelta
    from dnd_simulator.core.world import WorldState


class Layer(ABC):
    """Abstract base for all simulation layers.

    Layers are stacked from most abstract (geography) to most concrete (NPCs).
    Each layer can read state from layers below it, but never above.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this layer."""

    @abstractmethod
    def tick(self, delta: TimeDelta, world_state: WorldState) -> list[Event]:
        """Advance simulation by delta time. Returns events that occurred."""

    @abstractmethod
    def handle_event(self, event: Event) -> list[Event]:
        """Process an external event. May produce new events in response."""

    @abstractmethod
    def query(self, query: Query) -> Answer:
        """Answer a question about current state."""

    @abstractmethod
    def get_state(self) -> dict[str, object]:
        """Return serializable state for saving."""

    @abstractmethod
    def load_state(self, state: dict[str, object]) -> None:
        """Restore state from saved data."""
