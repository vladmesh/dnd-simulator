"""Tests for typed query accessors (core/queries.py) through real layers.

Each accessor builds the Query, dispatches via a QueryFn, and narrows the
answer once — consumers get typed payloads instead of hand-casting
``Answer.value``.
"""

import pytest

from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import Answer, FactionRelation, Query, QueryFn, QueryType
from dnd_simulator.core.queries import (
    NationInfo,
    RegionInfo,
    SettlementInfo,
    WeatherInfo,
    query_faction_name,
    query_faction_relation,
    query_is_daylight,
    query_location_region,
    query_nation_info,
    query_nations,
    query_region_info,
    query_region_owner,
    query_region_settlements,
    query_regions,
    query_weather,
)
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType, WeatherCondition
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.politics.models import Leader, LeaderTrait, Nation
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.layers.settlements.models import Settlement, SettlementType


def _make_query_fn(*layers: object) -> QueryFn:
    """Dispatch queries to real layer instances by name."""
    by_name = {layer.name: layer for layer in layers}  # type: ignore[attr-defined]

    def query_fn(layer_name: str, query: Query) -> Answer:
        answer = by_name[layer_name].query(query)  # type: ignore[attr-defined]
        assert isinstance(answer, Answer)
        return answer

    return query_fn


@pytest.fixture
def geography() -> GeographyLayer:
    region = Region(
        id="greenvale",
        name="Greenvale",
        latitude=45.0,
        longitude=10.0,
        elevation=200.0,
        terrain=TerrainType.FOREST,
        water_proximity=0.3,
        weather=WeatherCondition.LIGHT_RAIN,
        temperature=12.5,
    )
    graph = LocationGraph([Location(id="old_mill", name="Old Mill", region_id="greenvale")])
    return GeographyLayer(regions=[region], location_graph=graph)


@pytest.fixture
def politics() -> PoliticsLayer:
    nation = Nation(
        id="ardania",
        name="Ardania",
        regions=["greenvale"],
        wealth=60.0,
        military=40.0,
        stability=75.0,
        leader=Leader(name="Queen Mab", age=52, trait=LeaderTrait.DIPLOMAT),
    )
    return PoliticsLayer(
        nations=[nation],
        faction_relations={("bandits", "town_guard"): FactionRelation.HOSTILE},
        faction_names={"town_guard": "Town Guard"},
    )


@pytest.fixture
def settlements() -> SettlementsLayer:
    return SettlementsLayer(
        settlements=[
            Settlement(
                id="millbrook",
                name="Millbrook",
                region_id="greenvale",
                type=SettlementType.VILLAGE,
                population=300,
                prosperity=55.0,
                defenses=15.0,
            )
        ]
    )


class TestGeographyAccessors:
    def test_weather_comes_from_the_regions_current_state(self, geography: GeographyLayer) -> None:
        weather = query_weather(_make_query_fn(geography), region_id="greenvale")
        assert weather == WeatherInfo(condition="light_rain", temperature=12.5)

    def test_region_info_carries_full_region_data(self, geography: GeographyLayer) -> None:
        info = query_region_info(_make_query_fn(geography), region_id="greenvale")
        assert isinstance(info, RegionInfo)
        assert info.name == "Greenvale"
        assert info.terrain == "forest"
        assert info.latitude == 45.0

    def test_location_resolves_to_its_region(self, geography: GeographyLayer) -> None:
        assert query_location_region(_make_query_fn(geography), location_id="old_mill") == "greenvale"

    def test_unknown_location_resolves_to_none(self, geography: GeographyLayer) -> None:
        assert query_location_region(_make_query_fn(geography), location_id="nowhere") is None

    def test_regions_lists_all_region_ids(self, geography: GeographyLayer) -> None:
        assert query_regions(_make_query_fn(geography)) == ["greenvale"]

    def test_noon_at_mid_latitude_is_daylight_and_midnight_is_not(self, geography: GeographyLayer) -> None:
        query_fn = _make_query_fn(geography)
        assert query_is_daylight(query_fn, location_id="old_mill", month=6, hour=12) is True
        assert query_is_daylight(query_fn, location_id="old_mill", month=6, hour=0) is False


class TestPoliticsAccessors:
    def test_nation_info_includes_leader(self, politics: PoliticsLayer) -> None:
        info = query_nation_info(_make_query_fn(politics), nation_id="ardania")
        assert isinstance(info, NationInfo)
        assert info.name == "Ardania"
        assert info.wealth == 60.0
        assert info.leader is not None
        assert info.leader.name == "Queen Mab"
        assert info.leader.trait == "diplomat"

    def test_nations_lists_all_nation_ids(self, politics: PoliticsLayer) -> None:
        assert query_nations(_make_query_fn(politics)) == ["ardania"]

    def test_region_owner_is_the_controlling_nation(self, politics: PoliticsLayer) -> None:
        assert query_region_owner(_make_query_fn(politics), region_id="greenvale") == "ardania"

    def test_region_without_owner_returns_none(self, politics: PoliticsLayer) -> None:
        assert query_region_owner(_make_query_fn(politics), region_id="wildlands") is None

    def test_faction_relation_returns_the_enum(self, politics: PoliticsLayer) -> None:
        query_fn = _make_query_fn(politics)
        assert query_faction_relation(query_fn, "bandits", "town_guard") is FactionRelation.HOSTILE
        assert query_faction_relation(query_fn, "bandits", "bandits") is FactionRelation.FRIENDLY
        assert query_faction_relation(query_fn, "bandits", "strangers") is FactionRelation.NEUTRAL

    def test_faction_name_resolves_or_is_none(self, politics: PoliticsLayer) -> None:
        query_fn = _make_query_fn(politics)
        assert query_faction_name(query_fn, "town_guard") == "Town Guard"
        assert query_faction_name(query_fn, "unknown") is None


class TestSettlementsAccessors:
    def test_region_settlements_are_typed(self, settlements: SettlementsLayer) -> None:
        result = query_region_settlements(_make_query_fn(settlements), region_id="greenvale")
        assert result == [
            SettlementInfo(
                id="millbrook",
                name="Millbrook",
                region_id="greenvale",
                type="village",
                population=300,
                prosperity=55.0,
                defenses=15.0,
            )
        ]

    def test_region_without_settlements_is_empty(self, settlements: SettlementsLayer) -> None:
        assert query_region_settlements(_make_query_fn(settlements), region_id="wildlands") == []


class TestFailFast:
    def test_malformed_answer_raises_naming_the_query(self) -> None:
        def bogus_query_fn(layer_name: str, query: Query) -> Answer:
            return Answer(value=42)

        with pytest.raises(RuntimeError, match="WEATHER"):
            query_weather(bogus_query_fn, region_id="greenvale")

    def test_malformed_relation_raises_instead_of_degrading(self) -> None:
        def bogus_query_fn(layer_name: str, query: Query) -> Answer:
            return Answer(value="hostile")

        with pytest.raises(RuntimeError, match="FACTION_RELATION"):
            query_faction_relation(bogus_query_fn, "a", "b")

    def test_layer_errors_propagate_unchanged(self, geography: GeographyLayer) -> None:
        # Missing region is a domain error (KeyError), not a malformed answer —
        # accessors must not swallow or rewrap it.
        with pytest.raises(KeyError):
            query_weather(_make_query_fn(geography), region_id="missing")
        with pytest.raises(ValueError):
            _make_query_fn(geography)("geography", Query(question=QueryType.NATIONS))
