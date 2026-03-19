from __future__ import annotations

from dataclasses import dataclass, field

from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import Answer, Event, GameDateTime, Query, TimeDelta


@dataclass
class WorldState:
    """Snapshot of the world visible to layers during a tick."""

    time: GameDateTime
    layer_states: dict[str, dict[str, object]] = field(default_factory=dict)


class World:
    """Container for all simulation layers. Manages time and event propagation."""

    def __init__(self, layers: list[Layer], time: GameDateTime | None = None) -> None:
        self.time = time or GameDateTime()
        self._layers = layers

    @property
    def layers(self) -> list[Layer]:
        return list(self._layers)

    def get_state(self) -> WorldState:
        """Build current world state from all layers."""
        return WorldState(
            time=self.time,
            layer_states={layer.name: layer.get_state() for layer in self._layers},
        )

    def advance_time(self, delta: TimeDelta) -> list[Event]:
        """Advance world time. Ticks layers in order, propagates events."""
        self.time = self.time.advance(hours=delta.hours, days=delta.days)
        all_events: list[Event] = []

        for layer in self._layers:
            state = self.get_state()
            events = layer.tick(delta, state)
            all_events.extend(events)
            self._propagate_events(events, source=layer)

        return all_events

    def handle_event(self, event: Event) -> list[Event]:
        """Send an event to all layers and collect resulting events."""
        all_events: list[Event] = []
        for layer in self._layers:
            new_events = layer.handle_event(event)
            all_events.extend(new_events)
        return all_events

    def query_layer(self, layer_name: str, query: Query) -> Answer:
        """Query a specific layer by name."""
        for layer in self._layers:
            if layer.name == layer_name:
                return layer.query(query)
        raise ValueError(f"Layer '{layer_name}' not found")

    def _propagate_events(self, events: list[Event], source: Layer) -> None:
        """Send events to all layers except the source."""
        for event in events:
            for layer in self._layers:
                if layer is not source:
                    layer.handle_event(event)

    def save(self) -> dict[str, object]:
        """Serialize entire world state."""
        return {
            "time": {
                "year": self.time.year,
                "month": self.time.month,
                "day": self.time.day,
                "hour": self.time.hour,
                "minute": self.time.minute,
            },
            "layers": {layer.name: layer.get_state() for layer in self._layers},
        }

    def load(self, data: dict[str, object]) -> None:
        """Restore world from saved data."""
        time_data = data["time"]
        assert isinstance(time_data, dict)
        self.time = GameDateTime(**time_data)
        layers_data = data.get("layers", {})
        assert isinstance(layers_data, dict)
        for layer in self._layers:
            if layer.name in layers_data:
                state = layers_data[layer.name]
                assert isinstance(state, dict)
                layer.load_state(state)
