from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.creature_host import CreatureHost
from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, EmitFn, Event, GameDateTime, Query, QueryFn, TimeDelta

if TYPE_CHECKING:
    from dnd_simulator.core.location import LocationGraph

logger = structlog.get_logger(domain="world")


class LayerError(Exception):
    """Raised when a layer violates isolation rules."""


class World:
    """Container for all simulation layers. Manages time and event propagation."""

    def __init__(
        self,
        layers: list[Layer],
        time: GameDateTime | None = None,
        location_graph: LocationGraph | None = None,
    ) -> None:
        from dnd_simulator.core.location import LocationGraph as _LocationGraph

        self.time = time or GameDateTime()
        self._layers = layers
        self.location_graph = location_graph or _LocationGraph()
        self._last_tick_time: dict[str, GameDateTime] = {layer.name: self.time for layer in layers}
        self._layer_indices: dict[str, int] = {layer.name: i for i, layer in enumerate(layers)}

    @property
    def layers(self) -> list[Layer]:
        return list(self._layers)

    @property
    def creature_host(self) -> CreatureHost:
        """Return the registered CreatureHost (entities layer). Fail-fast if missing."""
        for layer in self._layers:
            if isinstance(layer, CreatureHost):
                return layer
        raise RuntimeError("World has no CreatureHost — entities layer must be registered")

    def advance_time(self, delta: TimeDelta) -> list[Event]:
        """Advance world time. Only ticks layers whose tick_interval has elapsed."""
        logger.debug("advance_time", delta_seconds=delta.seconds)
        self.time = self.time.advance(seconds=delta.seconds)
        now = self.time.to_total_seconds()
        all_events: list[Event] = []

        for layer in self._layers:
            last = self._last_tick_time[layer.name].to_total_seconds()
            elapsed = now - last

            if layer.tick_interval == 0 or elapsed >= layer.tick_interval:
                query_fn = self.make_query_fn(layer.name)
                emit_fn = self.make_emit_fn(layer.name)
                events = layer.tick(TimeDelta(seconds=elapsed), self.time, query_fn, emit_fn)
                all_events.extend(events)
                self._propagate_events(events, source=layer)
                self._last_tick_time[layer.name] = self.time

        return all_events

    def handle_event(self, event: Event) -> ActionResult:
        """Send an event to all layers. Returns first failure or aggregated success."""
        all_events: list[Event] = []
        for layer in self._layers:
            query_fn = self.make_query_fn(layer.name)
            emit_fn = self.make_emit_fn(layer.name)
            result = layer.handle_event(event, query_fn, emit_fn)
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

    def make_query_fn(self, caller_layer: str) -> QueryFn:
        """Create a query callback for a specific layer with validation."""
        caller_index = self._layer_indices[caller_layer]

        def query_fn(target_layer: str, query: Query) -> Answer:
            if target_layer == caller_layer:
                raise LayerError(f"{caller_layer} cannot query itself through World")
            target_index = self._layer_indices.get(target_layer)
            if target_index is None:
                raise LayerError(f"Layer '{target_layer}' not found")
            if target_index >= caller_index:
                raise LayerError(
                    f"{caller_layer} (index {caller_index}) cannot query "
                    f"{target_layer} (index {target_index}) — only layers below"
                )
            return self.query_layer(target_layer, query)

        return query_fn

    def make_emit_fn(self, caller_layer: str) -> EmitFn:
        """Create an emit callback for a specific layer with validation."""

        def emit_fn(event: Event) -> ActionResult:
            if event.source_layer != caller_layer:
                raise LayerError(f"{caller_layer} cannot emit event with source_layer='{event.source_layer}'")
            return self.handle_event(event)

        return emit_fn

    def _propagate_events(self, events: list[Event], source: Layer) -> None:
        """Send events to all layers except the source (notification, results ignored)."""
        for event in events:
            for layer in self._layers:
                if layer is not source:
                    query_fn = self.make_query_fn(layer.name)
                    emit_fn = self.make_emit_fn(layer.name)
                    layer.handle_event(event, query_fn, emit_fn)

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
