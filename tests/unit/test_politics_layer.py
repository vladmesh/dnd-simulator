"""Tests for the politics layer."""

import pytest

from dnd_simulator.core.events import WeatherChangedPayload
from dnd_simulator.core.models import ActionResult, Answer, GameDateTime, Query, QueryType, TimeDelta
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.politics.models import (
    DiplomaticStatus,
    Leader,
    LeaderTrait,
    Nation,
)

_TIME = GameDateTime(year=1490, month=6, day=1, hour=12)


def _noop_query_fn(layer: str, query: Query) -> Answer:
    raise RuntimeError(f"Politics should not query other layers: {layer}/{query.question}")


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _make_nations() -> list[Nation]:
    return [
        Nation(
            id="alpha",
            name="Kingdom of Alpha",
            regions=["region_a", "region_b"],
            wealth=60.0,
            military=50.0,
            stability=70.0,
            leader=Leader(name="King Test", age=40, trait=LeaderTrait.MERCHANT),
        ),
        Nation(
            id="beta",
            name="Republic of Beta",
            regions=["region_c", "region_d"],
            wealth=40.0,
            military=60.0,
            stability=60.0,
            leader=Leader(name="General Test", age=35, trait=LeaderTrait.MILITARIST),
        ),
    ]


def _make_layer(seed: int = 42) -> PoliticsLayer:
    return PoliticsLayer(
        nations=_make_nations(),
        region_terrains={
            "region_a": "coast",
            "region_b": "plains",
            "region_c": "mountains",
            "region_d": "hills",
        },
        region_adjacency={
            "region_a": ["region_b"],
            "region_b": ["region_a", "region_c"],
            "region_c": ["region_b", "region_d"],
            "region_d": ["region_c"],
        },
        seed=seed,
    )


class TestLayerBasics:
    def test_name(self) -> None:
        layer = _make_layer()
        assert layer.name == "politics"

    def test_handle_event_empty(self) -> None:
        from dnd_simulator.core.models import Event, EventType

        layer = _make_layer()
        result = layer.handle_event(
            Event(
                event_type=EventType.WEATHER_CHANGED,
                source_layer="geography",
                data=WeatherChangedPayload("r1", "clear", "rain", 10.0),
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        assert result.success
        assert result.events == []


class TestRelations:
    def test_default_peace(self) -> None:
        layer = _make_layer()
        assert layer.get_relation("alpha", "beta") == DiplomaticStatus.PEACE

    def test_set_war(self) -> None:
        layer = _make_layer()
        layer.set_relation("alpha", "beta", DiplomaticStatus.WAR)
        assert layer.get_relation("alpha", "beta") == DiplomaticStatus.WAR
        # Symmetric
        assert layer.get_relation("beta", "alpha") == DiplomaticStatus.WAR

    def test_set_trade(self) -> None:
        layer = _make_layer()
        layer.set_relation("alpha", "beta", DiplomaticStatus.TRADE_AGREEMENT)
        assert layer.get_relation("alpha", "beta") == DiplomaticStatus.TRADE_AGREEMENT


class TestRegionOwner:
    def test_owned_region(self) -> None:
        layer = _make_layer()
        assert layer.get_region_owner("region_a") == "alpha"
        assert layer.get_region_owner("region_c") == "beta"

    def test_unowned_region(self) -> None:
        layer = _make_layer()
        assert layer.get_region_owner("unknown") is None


class TestTick:
    def test_monthly_tick_runs(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta.from_days(30), _TIME, _noop_query_fn, _noop_emit_fn)
        # Economy should have changed wealth
        info = layer.query(Query(question=QueryType.NATION_INFO, params={"nation_id": "alpha"}))
        assert info.value.wealth != 60.0  # Should have changed from income/upkeep

    def test_multiple_months(self) -> None:
        layer = _make_layer()
        layer.tick(TimeDelta.from_days(90), _TIME, _noop_query_fn, _noop_emit_fn)
        # Should have processed 3 monthly ticks
        info = layer.query(Query(question=QueryType.NATION_INFO, params={"nation_id": "alpha"}))
        # Wealth should have changed significantly over 3 months
        assert info.value.wealth != 60.0


class TestWarResolution:
    def test_war_causes_region_change(self) -> None:
        """Over many months of war, regions should change hands."""
        layer = _make_layer(seed=123)
        layer.set_relation("alpha", "beta", DiplomaticStatus.WAR)

        # Run 12 months of war
        all_events = []
        for _ in range(12):
            events = layer.tick(TimeDelta.from_days(30), _TIME, _noop_query_fn, _noop_emit_fn)
            all_events.extend(events)

        # At least some conquest or political events should have occurred
        assert len(all_events) > 0
        # Check that region_conquered events exist
        conquest_events = [e for e in all_events if e.data.get("type") == "region_conquered"]
        assert len(conquest_events) > 0

    def test_war_reduces_military(self) -> None:
        layer = _make_layer(seed=42)
        layer.set_relation("alpha", "beta", DiplomaticStatus.WAR)

        def military(nation_id: str) -> float:
            return layer.query(Query(question=QueryType.NATION_INFO, params={"nation_id": nation_id})).value.military

        alpha_mil = military("alpha")
        beta_mil = military("beta")

        layer.tick(TimeDelta.from_days(30), _TIME, _noop_query_fn, _noop_emit_fn)

        alpha_mil_after = military("alpha")
        beta_mil_after = military("beta")

        # Both should lose military in war
        assert alpha_mil_after < alpha_mil
        assert beta_mil_after < beta_mil


class TestQueries:
    def test_nations_list(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question=QueryType.NATIONS, params={}))
        assert sorted(result.value) == ["alpha", "beta"]

    def test_nation_info(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question=QueryType.NATION_INFO, params={"nation_id": "alpha"}))
        assert result.value.name == "Kingdom of Alpha"
        assert result.value.wealth == 60.0
        assert result.value.leader is not None
        assert result.value.leader.trait == "merchant"

    def test_relations_query(self) -> None:
        layer = _make_layer()
        layer.set_relation("alpha", "beta", DiplomaticStatus.WAR)
        result = layer.query(Query(question=QueryType.RELATIONS, params={"nation_id": "alpha"}))
        assert len(result.value) == 1
        assert result.value[0]["nation"] == "beta"
        assert result.value[0]["status"] == "war"

    def test_region_owner_query(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question=QueryType.REGION_OWNER, params={"region_id": "region_a"}))
        assert result.value == "alpha"

    def test_unknown_query(self) -> None:
        layer = _make_layer()
        with pytest.raises(ValueError, match="Unknown politics query"):
            layer.query(Query(question="nonsense", params={}))


class TestSaveLoad:
    def test_round_trip(self) -> None:
        layer = _make_layer()
        layer.set_relation("alpha", "beta", DiplomaticStatus.WAR)

        state = layer.get_state()

        new_layer = PoliticsLayer(
            region_terrains={"region_a": "coast", "region_b": "plains", "region_c": "mountains", "region_d": "hills"},
            region_adjacency={
                "region_a": ["region_b"],
                "region_b": ["region_a", "region_c"],
                "region_c": ["region_b", "region_d"],
                "region_d": ["region_c"],
            },
        )
        new_layer.load_state(state)

        # Check nations restored
        result = new_layer.query(Query(question=QueryType.NATIONS, params={}))
        assert sorted(result.value) == ["alpha", "beta"]

        # Check relations restored
        assert new_layer.get_relation("alpha", "beta") == DiplomaticStatus.WAR

        # Check nation data restored
        info = new_layer.query(Query(question=QueryType.NATION_INFO, params={"nation_id": "alpha"}))
        assert info.value.name == "Kingdom of Alpha"
        assert info.value.leader is not None
        assert info.value.leader.name == "King Test"
