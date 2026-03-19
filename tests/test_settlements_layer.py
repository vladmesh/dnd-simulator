"""Tests for the settlements layer."""

import pytest

from dnd_simulator.core.models import Event, EventType, GameDateTime, Query, TimeDelta
from dnd_simulator.core.world import WorldState
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.layers.settlements.models import Settlement, SettlementType


def _make_settlements() -> list[Settlement]:
    return [
        Settlement(
            id="city_a",
            name="Port City",
            region_id="region_a",
            type=SettlementType.CITY,
            population=5000,
            prosperity=70.0,
            defenses=60.0,
        ),
        Settlement(
            id="village_a",
            name="Farm Village",
            region_id="region_a",
            type=SettlementType.VILLAGE,
            population=200,
            prosperity=50.0,
            defenses=10.0,
        ),
        Settlement(
            id="town_b",
            name="Mountain Town",
            region_id="region_b",
            type=SettlementType.TOWN,
            population=800,
            prosperity=50.0,
            defenses=40.0,
        ),
    ]


def _make_layer() -> SettlementsLayer:
    return SettlementsLayer(
        settlements=_make_settlements(),
        region_terrains={"region_a": "coast", "region_b": "mountains"},
    )


def _world_state(
    weather_a: str = "clear",
    weather_b: str = "clear",
    nation_wealth: float = 50.0,
    nation_stability: float = 70.0,
) -> WorldState:
    return WorldState(
        time=GameDateTime(year=1490, month=6, day=1, hour=12),
        layer_states={
            "geography": {
                "regions": {
                    "region_a": {"weather": weather_a, "terrain": "coast"},
                    "region_b": {"weather": weather_b, "terrain": "mountains"},
                },
            },
            "politics": {
                "nations": {
                    "alpha": {
                        "regions": ["region_a"],
                        "wealth": nation_wealth,
                        "stability": nation_stability,
                    },
                    "beta": {
                        "regions": ["region_b"],
                        "wealth": 40.0,
                        "stability": 60.0,
                    },
                },
            },
        },
    )


class TestLayerBasics:
    def test_name(self) -> None:
        layer = _make_layer()
        assert layer.name == "settlements"

    def test_handle_event_unrelated(self) -> None:
        layer = _make_layer()
        event = Event(event_type=EventType.WEATHER_CHANGED, source_layer="geography")
        assert layer.handle_event(event) == []


class TestRegionIncome:
    def test_income_from_coast_region(self) -> None:
        layer = _make_layer()
        income = layer.get_region_income("region_a")
        # city: 8.0 * 1.3 * 0.7 = 7.28 -> 7.3
        # village: 1.5 * 1.3 * 0.5 = 0.975 -> 1.0
        assert income > 0
        assert income == pytest.approx(7.3 + 1.0, abs=0.1)

    def test_income_from_mountain_region(self) -> None:
        layer = _make_layer()
        income = layer.get_region_income("region_b")
        # town: 4.0 * 1.0 * 0.5 = 2.0
        assert income == pytest.approx(2.0, abs=0.1)

    def test_empty_region_no_income(self) -> None:
        layer = _make_layer()
        assert layer.get_region_income("unknown") == 0.0


class TestTick:
    def test_no_tick_for_short_time(self) -> None:
        layer = _make_layer()
        events = layer.tick(TimeDelta(hours=24), _world_state())
        assert events == []

    def test_monthly_tick_changes_population(self) -> None:
        layer = _make_layer()
        ws = _world_state()
        # 30 days = 720 hours
        layer.tick(TimeDelta(days=30), ws)
        info = layer.query(Query(question="settlement_info", params={"settlement_id": "city_a"}))
        # prosperity 70 -> population should grow (2%)
        assert info.value["population"] > 5000

    def test_bad_weather_hurts_village_prosperity(self) -> None:
        layer = _make_layer()
        ws = _world_state(weather_a="blizzard")
        layer.tick(TimeDelta(days=30), ws)
        info = layer.query(Query(question="settlement_info", params={"settlement_id": "village_a"}))
        # Blizzard should hurt village prosperity significantly
        assert info.value["prosperity"] < 50.0

    def test_bad_weather_barely_affects_city(self) -> None:
        layer = _make_layer()
        ws = _world_state(weather_a="blizzard")
        layer.tick(TimeDelta(days=30), ws)
        info = layer.query(Query(question="settlement_info", params={"settlement_id": "city_a"}))
        # City barely affected by weather
        # Blizzard: -5.0 * 0.3 = -1.5 on prosperity, plus drift from wealth/stability
        assert info.value["prosperity"] > 60.0


class TestConquest:
    def test_conquest_damages_settlements(self) -> None:
        layer = _make_layer()
        event = Event(
            event_type=EventType.CUSTOM,
            source_layer="politics",
            data={"type": "region_conquered", "winner": "beta", "loser": "alpha", "region": "region_a"},
        )
        result_events = layer.handle_event(event)
        # Both settlements in region_a should be damaged
        assert len(result_events) == 2

        info = layer.query(Query(question="settlement_info", params={"settlement_id": "city_a"}))
        assert info.value["prosperity"] < 70.0  # was 70
        assert info.value["defenses"] < 60.0  # was 60
        assert info.value["population"] < 5000  # was 5000

    def test_conquest_doesnt_affect_other_regions(self) -> None:
        layer = _make_layer()
        event = Event(
            event_type=EventType.CUSTOM,
            source_layer="politics",
            data={"type": "region_conquered", "winner": "alpha", "loser": "beta", "region": "region_a"},
        )
        layer.handle_event(event)

        info = layer.query(Query(question="settlement_info", params={"settlement_id": "town_b"}))
        assert info.value["prosperity"] == 50.0  # unchanged


class TestQueries:
    def test_settlements_list(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="settlements", params={}))
        assert sorted(result.value) == ["city_a", "town_b", "village_a"]

    def test_settlement_info(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="settlement_info", params={"settlement_id": "city_a"}))
        assert result.value["name"] == "Port City"
        assert result.value["type"] == "city"
        assert result.value["population"] == 5000

    def test_region_settlements(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="region_settlements", params={"region_id": "region_a"}))
        assert len(result.value) == 2
        names = {s["name"] for s in result.value}
        assert names == {"Port City", "Farm Village"}

    def test_region_income_query(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question="region_income", params={"region_id": "region_a"}))
        assert result.value > 0

    def test_unknown_query(self) -> None:
        layer = _make_layer()
        with pytest.raises(ValueError, match="Unknown settlements query"):
            layer.query(Query(question="nonsense", params={}))


class TestSaveLoad:
    def test_round_trip(self) -> None:
        layer = _make_layer()
        state = layer.get_state()

        new_layer = SettlementsLayer(region_terrains={"region_a": "coast", "region_b": "mountains"})
        new_layer.load_state(state)

        result = new_layer.query(Query(question="settlements", params={}))
        assert sorted(result.value) == ["city_a", "town_b", "village_a"]

        info = new_layer.query(Query(question="settlement_info", params={"settlement_id": "city_a"}))
        assert info.value["name"] == "Port City"
        assert info.value["population"] == 5000
