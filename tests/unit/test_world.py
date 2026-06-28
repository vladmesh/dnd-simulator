"""Tests for World layer isolation, event propagation, tick gating, and save/load."""

from __future__ import annotations

import pytest

from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import (
    ActionResult,
    Answer,
    EmitFn,
    Event,
    EventType,
    GameDateTime,
    Query,
    QueryFn,
    QueryType,
    TimeDelta,
)
from dnd_simulator.core.world import LayerError, World


class StubLayer(Layer):
    """Minimal Layer implementation for testing World behavior."""

    def __init__(self, layer_name: str, interval: int = 0, answer: object = None) -> None:
        self._name = layer_name
        self._interval = interval
        self._answer = answer
        self.tick_calls: list[TimeDelta] = []
        self.handled_events: list[Event] = []
        self.tick_events: list[Event] = []  # events returned from tick()
        self._state: dict[str, object] = {}
        self.load_state_calls: list[dict[str, object]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def tick_interval(self) -> int:
        return self._interval

    def tick(self, delta: TimeDelta, time: GameDateTime, query_fn: QueryFn, emit_fn: EmitFn) -> list[Event]:
        self.tick_calls.append(delta)
        return list(self.tick_events)

    def handle_event(self, event: Event, query_fn: QueryFn, emit_fn: EmitFn) -> ActionResult:
        self.handled_events.append(event)
        return ActionResult(success=True)

    def query(self, query: Query) -> Answer:
        return Answer(value=self._answer)

    def get_state(self) -> dict[str, object]:
        return dict(self._state)

    def load_state(self, state: dict[str, object]) -> None:
        self.load_state_calls.append(state)
        self._state = dict(state)


class TestLayerIsolationQueryDirection:
    """make_query_fn enforces layers-depend-down invariant."""

    def _make_world(self) -> World:
        return World(
            [
                StubLayer("geography", answer="forest"),
                StubLayer("politics", answer="kingdom"),
                StubLayer("entities", answer="hero"),
            ]
        )

    def test_entities_queries_geography_succeeds(self) -> None:
        world = self._make_world()
        query_fn = world.make_query_fn("entities")
        result = query_fn("geography", Query(question=QueryType.LOCATION_REGION))
        assert result.value == "forest"

    def test_entities_queries_politics_succeeds(self) -> None:
        world = self._make_world()
        query_fn = world.make_query_fn("entities")
        result = query_fn("politics", Query(question=QueryType.REGION_OWNER))
        assert result.value == "kingdom"

    def test_entities_queries_itself_raises_layer_error(self) -> None:
        world = self._make_world()
        query_fn = world.make_query_fn("entities")
        with pytest.raises(LayerError, match="cannot query itself"):
            query_fn("entities", Query(question=QueryType.LOCATION_REGION))

    def test_geography_queries_entities_raises_layer_error(self) -> None:
        world = self._make_world()
        query_fn = world.make_query_fn("geography")
        with pytest.raises(LayerError, match="only layers below"):
            query_fn("entities", Query(question=QueryType.LOCATION_REGION))

    def test_politics_queries_entities_raises_layer_error(self) -> None:
        world = self._make_world()
        query_fn = world.make_query_fn("politics")
        with pytest.raises(LayerError, match="only layers below"):
            query_fn("entities", Query(question=QueryType.LOCATION_REGION))

    def test_query_nonexistent_layer_raises_layer_error(self) -> None:
        world = self._make_world()
        query_fn = world.make_query_fn("entities")
        with pytest.raises(LayerError, match="not found"):
            query_fn("magic", Query(question=QueryType.LOCATION_REGION))


class TestLayerIsolationEmitValidation:
    """make_emit_fn validates event source_layer matches caller."""

    def test_emit_with_matching_source_propagates(self) -> None:
        geo = StubLayer("geography")
        ent = StubLayer("entities")
        world = World([geo, ent])

        emit_fn = world.make_emit_fn("geography")
        event = Event(event_type=EventType.ENTITY_MOVE, source_layer="geography")
        result = emit_fn(event)
        assert result.success is True

    def test_emit_with_mismatched_source_raises_layer_error(self) -> None:
        geo = StubLayer("geography")
        ent = StubLayer("entities")
        world = World([geo, ent])

        emit_fn = world.make_emit_fn("geography")
        event = Event(event_type=EventType.ENTITY_MOVE, source_layer="entities")
        with pytest.raises(LayerError, match="cannot emit event"):
            emit_fn(event)


class TestEventPropagation:
    """Events from tick are delivered to all layers except the source."""

    def test_tick_events_propagated_to_other_layers_not_source(self) -> None:
        geo = StubLayer("geography")
        pol = StubLayer("politics")
        ent = StubLayer("entities")
        world = World([geo, pol, ent])

        event = Event(event_type=EventType.ENTITY_MOVE, source_layer="geography")
        geo.tick_events = [event]

        world.advance_time(TimeDelta(seconds=10))

        # Source (geo) should NOT receive its own event via propagation
        assert event not in geo.handled_events
        # Other layers should receive the event
        assert event in pol.handled_events
        assert event in ent.handled_events

    def test_propagation_reaches_all_non_source_layers(self) -> None:
        layers = [StubLayer(f"layer_{i}") for i in range(4)]
        world = World(layers)

        event = Event(event_type=EventType.ENTITY_SAY, source_layer="layer_1")
        layers[1].tick_events = [event]

        world.advance_time(TimeDelta(seconds=10))

        # layer_1 (source) should not get the event
        assert event not in layers[1].handled_events
        # All others should
        for i in [0, 2, 3]:
            assert event in layers[i].handled_events


class TestAdvanceTimeTickGating:
    """advance_time only ticks layers when their tick_interval has elapsed."""

    def test_interval_zero_ticked_every_call(self) -> None:
        layer = StubLayer("always", interval=0)
        world = World([layer])

        world.advance_time(TimeDelta(seconds=10))
        world.advance_time(TimeDelta(seconds=5))
        assert len(layer.tick_calls) == 2

    def test_interval_not_elapsed_skips_tick(self) -> None:
        layer = StubLayer("slow", interval=100)
        world = World([layer])

        world.advance_time(TimeDelta(seconds=50))
        assert len(layer.tick_calls) == 0

    def test_interval_elapsed_triggers_tick(self) -> None:
        layer = StubLayer("slow", interval=100)
        world = World([layer])

        world.advance_time(TimeDelta(seconds=100))
        assert len(layer.tick_calls) == 1

    def test_last_tick_time_updated_prevents_retick(self) -> None:
        layer = StubLayer("slow", interval=100)
        world = World([layer])

        world.advance_time(TimeDelta(seconds=100))
        assert len(layer.tick_calls) == 1

        # Only 50 more seconds — not enough for another tick
        world.advance_time(TimeDelta(seconds=50))
        assert len(layer.tick_calls) == 1

        # 50 more (total 100 since last tick) — should tick again
        world.advance_time(TimeDelta(seconds=50))
        assert len(layer.tick_calls) == 2


class TestSaveLoadRoundTrip:
    """World save/load preserves time, last_tick_times, and layer state."""

    def test_save_load_round_trip(self) -> None:
        geo = StubLayer("geography")
        geo._state = {"terrain": "forest"}
        pol = StubLayer("politics", interval=100)
        pol._state = {"ruler": "king"}

        world = World([geo, pol], time=GameDateTime(year=1490, month=6, day=15, hour=10))
        world.advance_time(TimeDelta(seconds=3600))  # +1 hour

        saved = world.save()

        # Load into fresh world with same layer structure
        geo2 = StubLayer("geography")
        pol2 = StubLayer("politics", interval=100)
        world2 = World([geo2, pol2])
        world2.load(saved)

        assert world2.time.year == 1490
        assert world2.time.month == 6
        assert world2.time.day == 15
        assert world2.time.hour == 11
        assert len(geo2.load_state_calls) == 1
        assert geo2.load_state_calls[0] == {"terrain": "forest"}
        assert len(pol2.load_state_calls) == 1
        assert pol2.load_state_calls[0] == {"ruler": "king"}

        # Last tick times restored — verify by checking that advancing 50s doesn't retick politics (interval=100)
        pol2_tick_count_before = len(pol2.tick_calls)
        world2.advance_time(TimeDelta(seconds=50))
        assert len(pol2.tick_calls) == pol2_tick_count_before


class TestQueryLayerPublicAPI:
    """query_layer delegates to the named layer's query method."""

    def test_query_layer_delegates_to_layer(self) -> None:
        geo = StubLayer("geography", answer="mountain_region")
        world = World([geo])

        result = world.query_layer("geography", Query(question=QueryType.LOCATION_REGION))
        assert result.value == "mountain_region"

    def test_query_layer_nonexistent_raises_value_error(self) -> None:
        geo = StubLayer("geography")
        world = World([geo])

        with pytest.raises(ValueError, match="not found"):
            world.query_layer("nonexistent", Query(question=QueryType.LOCATION_REGION))
