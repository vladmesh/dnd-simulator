"""Tests for the politics layer."""

import pytest

from dnd_simulator.core.models import GameDateTime, Query, TimeDelta
from dnd_simulator.core.world import WorldState
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.politics.models import (
    DiplomaticStatus,
    Leader,
    LeaderTrait,
    Nation,
)


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


def _world_state() -> WorldState:
    return WorldState(time=GameDateTime(year=1490, month=6, day=1, hour=12))


class TestLayerBasics:
    def test_name(self) -> None:
        layer = _make_layer()
        assert layer.name == "politics"

    def test_handle_event_empty(self) -> None:
        from dnd_simulator.core.models import Event, EventType

        layer = _make_layer()
        result = layer.handle_event(Event(event_type=EventType.WEATHER_CHANGED, source_layer="geography"))
        assert result == []


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
    def test_no_tick_for_short_time(self) -> None:
        layer = _make_layer()
        events = layer.tick(TimeDelta(hours=24), _world_state())
        assert events == []  # Need 720 hours for a monthly tick

    def test_monthly_tick_runs(self) -> None:
        layer = _make_layer()
        # 30 days = 720 hours
        layer.tick(TimeDelta(days=30), _world_state())
        # Economy should have changed wealth
        info = layer.query(Query(question="nation_info", params={"nation_id": "alpha"}))
        assert info.value["wealth"] != 60.0  # Should have changed from income/upkeep

    def test_multiple_months(self) -> None:
        layer = _make_layer()
        # 90 days = 3 months
        layer.tick(TimeDelta(days=90), _world_state())
        # Should have processed 3 monthly ticks
        info = layer.query(Query(question="nation_info", params={"nation_id": "alpha"}))
        # Wealth should have changed significantly over 3 months
        assert info.value["wealth"] != 60.0


class TestWarResolution:
    def test_war_causes_region_change(self) -> None:
        """Over many months of war, regions should change hands."""
        layer = _make_layer(seed=123)
        layer.set_relation("alpha", "beta", DiplomaticStatus.WAR)

        # Run 12 months of war
        all_events = []
        for _ in range(12):
            events = layer.tick(TimeDelta(days=30), _world_state())
            all_events.extend(events)

        # At least some conquest or political events should have occurred
        assert len(all_events) > 0
        # Check that region_conquered events exist
        conquest_events = [e for e in all_events if e.data.get("type") == "region_conquered"]
        assert len(conquest_events) > 0

    def test_war_reduces_military(self) -> None:
        layer = _make_layer(seed=42)
        layer.set_relation("alpha", "beta", DiplomaticStatus.WAR)

        alpha_mil = layer.query(Query(question="nation_info", params={"nation_id": "alpha"})).value["military"]
        beta_mil = layer.query(Query(question="nation_info", params={"nation_id": "beta"})).value["military"]

        layer.tick(TimeDelta(days=30), _world_state())

        alpha_mil_after = layer.query(Query(question="nation_info", params={"nation_id": "alpha"})).value["military"]
        beta_mil_after = layer.query(Query(question="nation_info", params={"nation_id": "beta"})).value["military"]

        # Both should lose military in war
        assert alpha_mil_after < alpha_mil
        assert beta_mil_after < beta_mil


class TestQueries:
    def test_nations_list(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="nations", params={}))
        assert sorted(result.value) == ["alpha", "beta"]

    def test_nation_info(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="nation_info", params={"nation_id": "alpha"}))
        assert result.value["name"] == "Kingdom of Alpha"
        assert result.value["wealth"] == 60.0
        assert result.value["leader"]["trait"] == "merchant"

    def test_relations_query(self) -> None:
        layer = _make_layer()
        layer.set_relation("alpha", "beta", DiplomaticStatus.WAR)
        result = layer.query(Query(question="relations", params={"nation_id": "alpha"}))
        assert len(result.value) == 1
        assert result.value[0]["nation"] == "beta"
        assert result.value[0]["status"] == "war"

    def test_region_owner_query(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="region_owner", params={"region_id": "region_a"}))
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
        result = new_layer.query(Query(question="nations", params={}))
        assert sorted(result.value) == ["alpha", "beta"]

        # Check relations restored
        assert new_layer.get_relation("alpha", "beta") == DiplomaticStatus.WAR

        # Check nation data restored
        info = new_layer.query(Query(question="nation_info", params={"nation_id": "alpha"}))
        assert info.value["name"] == "Kingdom of Alpha"
        assert info.value["leader"]["name"] == "King Test"
