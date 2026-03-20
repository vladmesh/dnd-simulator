from __future__ import annotations

from dataclasses import dataclass, field

from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, GameDateTime, Query, TimeDelta


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
        self._last_tick_time: dict[str, GameDateTime] = {layer.name: self.time for layer in layers}

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
        """Advance world time. Only ticks layers whose tick_interval has elapsed."""
        self.time = self.time.advance(seconds=delta.seconds)
        now = self.time.to_total_seconds()
        all_events: list[Event] = []

        for layer in self._layers:
            last = self._last_tick_time[layer.name].to_total_seconds()
            elapsed = now - last

            if layer.tick_interval == 0 or elapsed >= layer.tick_interval:
                state = self.get_state()
                events = layer.tick(TimeDelta(seconds=elapsed), state)
                all_events.extend(events)
                self._propagate_events(events, source=layer)
                self._last_tick_time[layer.name] = self.time

        return all_events

    def handle_event(self, event: Event) -> ActionResult:
        """Send an event to all layers. Returns first failure or aggregated success."""
        all_events: list[Event] = []
        for layer in self._layers:
            result = layer.handle_event(event)
            if not result.success:
                return result
            all_events.extend(result.events)
        return ActionResult(success=True, events=all_events)

    def query_layer(self, layer_name: str, query: Query) -> Answer:
        """Query a specific layer by name."""
        for layer in self._layers:
            if layer.name == layer_name:
                return layer.query(query)
        raise ValueError(f"Layer '{layer_name}' not found")

    def _propagate_events(self, events: list[Event], source: Layer) -> None:
        """Send events to all layers except the source (notification, results ignored)."""
        for event in events:
            for layer in self._layers:
                if layer is not source:
                    layer.handle_event(event)

    def save(self) -> dict[str, object]:
        """Serialize entire world state."""
        last_ticks: dict[str, dict[str, int]] = {}
        for name, t in self._last_tick_time.items():
            last_ticks[name] = {
                "year": t.year,
                "month": t.month,
                "day": t.day,
                "hour": t.hour,
                "minute": t.minute,
                "second": t.second,
            }

        return {
            "time": {
                "year": self.time.year,
                "month": self.time.month,
                "day": self.time.day,
                "hour": self.time.hour,
                "minute": self.time.minute,
                "second": self.time.second,
            },
            "last_tick_times": last_ticks,
            "layers": {layer.name: layer.get_state() for layer in self._layers},
        }

    def load(self, data: dict[str, object]) -> None:
        """Restore world from saved data."""
        time_data = data["time"]
        assert isinstance(time_data, dict)
        # Backward compat: old saves may lack 'second'
        self.time = GameDateTime(
            year=int(time_data.get("year", 1)),
            month=int(time_data.get("month", 1)),
            day=int(time_data.get("day", 1)),
            hour=int(time_data.get("hour", 0)),
            minute=int(time_data.get("minute", 0)),
            second=int(time_data.get("second", 0)),
        )

        # Restore last tick times (fallback to current time for old saves)
        last_ticks_data = data.get("last_tick_times", {})
        assert isinstance(last_ticks_data, dict)
        for layer in self._layers:
            lt = last_ticks_data.get(layer.name)
            if lt and isinstance(lt, dict):
                self._last_tick_time[layer.name] = GameDateTime(
                    year=int(lt.get("year", 1)),
                    month=int(lt.get("month", 1)),
                    day=int(lt.get("day", 1)),
                    hour=int(lt.get("hour", 0)),
                    minute=int(lt.get("minute", 0)),
                    second=int(lt.get("second", 0)),
                )
            else:
                self._last_tick_time[layer.name] = self.time

        layers_data = data.get("layers", {})
        assert isinstance(layers_data, dict)
        for layer in self._layers:
            if layer.name in layers_data:
                state = layers_data[layer.name]
                assert isinstance(state, dict)
                layer.load_state(state)
