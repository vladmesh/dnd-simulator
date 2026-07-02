"""Tests for awareness_builder exception narrowing — unexpected exceptions propagate."""

from __future__ import annotations

import pytest

from dnd_simulator.core.character import Ability, Attack, Character, DamageComponent, DamageType
from dnd_simulator.core.models import Answer, FactionRelation, GameDateTime, Query, QueryType
from dnd_simulator.core.queries import RegionInfo, WeatherInfo
from dnd_simulator.layers.entities.layer import EntitiesLayer

_TIME = GameDateTime(year=1490, month=6, day=15, hour=14)

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)


def _region_info(name: str) -> RegionInfo:
    return RegionInfo(
        id=name.lower().replace(" ", "_"),
        name=name,
        latitude=45.0,
        longitude=0.0,
        elevation=100.0,
        terrain="forest",
        water_proximity=0.0,
        weather="clear",
        temperature=15.0,
    )


class TestUnexpectedExceptionsPropagateInPeacefulAwareness:
    """Unexpected exceptions (TypeError, AttributeError, etc.) must NOT be swallowed."""

    def test_type_error_in_region_query_propagates(self) -> None:
        player = Character(id="p1", name="Hero", location_id="village")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                raise TypeError("unexpected bug in layer code")
            return Answer(value=None)

        with pytest.raises(TypeError, match="unexpected bug"):
            layer.build_awareness(player, _TIME, query_fn)

    def test_attribute_error_in_weather_query_propagates(self) -> None:
        player = Character(id="p1", name="Hero", location_id="village")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                return Answer(value="northern_region")
            if target == "geography" and query.question == QueryType.REGION_INFO:
                return Answer(value=_region_info("North"))
            if target == "geography" and query.question == QueryType.WEATHER:
                raise AttributeError("buggy attribute access")
            return Answer(value=None)

        with pytest.raises(AttributeError, match="buggy attribute"):
            layer.build_awareness(player, _TIME, query_fn)

    def test_runtime_error_in_settlements_query_propagates(self) -> None:
        player = Character(id="p1", name="Hero", location_id="village")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                return Answer(value="region1")
            if target == "geography" and query.question == QueryType.REGION_INFO:
                return Answer(value=_region_info("Region"))
            if target == "geography" and query.question == QueryType.WEATHER:
                return Answer(value=WeatherInfo(condition="clear", temperature=15))
            if target == "settlements":
                raise RuntimeError("unexpected settlements bug")
            return Answer(value=None)

        with pytest.raises(RuntimeError, match="unexpected settlements bug"):
            layer.build_awareness(player, _TIME, query_fn)

    def test_runtime_error_in_politics_query_propagates(self) -> None:
        player = Character(id="p1", name="Hero", location_id="village")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                return Answer(value="region1")
            if target == "geography" and query.question == QueryType.REGION_INFO:
                return Answer(value=_region_info("Region"))
            if target == "geography" and query.question == QueryType.WEATHER:
                return Answer(value=WeatherInfo(condition="clear", temperature=15))
            if target == "settlements":
                return Answer(value=[])
            if target == "politics":
                raise RuntimeError("politics layer bug")
            return Answer(value=None)

        with pytest.raises(RuntimeError, match="politics layer bug"):
            layer.build_awareness(player, _TIME, query_fn)


class TestExpectedExceptionsHandledGracefully:
    """Expected query failures (KeyError, ValueError, LayerError) degrade gracefully."""

    def test_key_error_in_region_query_uses_defaults(self) -> None:
        player = Character(id="p1", name="Hero", location_id="village")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                raise KeyError("region_id")
            return Answer(value=None)

        awareness = layer.build_awareness(player, _TIME, query_fn)
        assert awareness.region_name == "village"
        assert awareness.weather["condition"] == "clear"

    def test_value_error_in_weather_query_uses_defaults(self) -> None:
        player = Character(id="p1", name="Hero", location_id="village")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                return Answer(value="region1")
            if target == "geography" and query.question == QueryType.REGION_INFO:
                return Answer(value=_region_info("Region"))
            if target == "geography" and query.question == QueryType.WEATHER:
                raise ValueError("unknown query type")
            if target == "settlements" and query.question == QueryType.REGION_SETTLEMENTS:
                return Answer(value=[])
            return Answer(value=None)

        awareness = layer.build_awareness(player, _TIME, query_fn)
        assert awareness.weather["condition"] == "clear"

    def test_layer_error_in_politics_handled(self) -> None:
        from dnd_simulator.core.world import LayerError

        player = Character(id="p1", name="Hero", location_id="village")
        layer = EntitiesLayer([player])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "geography" and query.question == QueryType.LOCATION_REGION:
                return Answer(value="region1")
            if target == "geography" and query.question == QueryType.REGION_INFO:
                return Answer(value=_region_info("Region"))
            if target == "geography" and query.question == QueryType.WEATHER:
                return Answer(value=WeatherInfo(condition="clear", temperature=15))
            if target == "settlements":
                return Answer(value=[])
            if target == "politics":
                raise LayerError("politics layer not found")
            return Answer(value=None)

        awareness = layer.build_awareness(player, _TIME, query_fn)
        assert awareness.territory_owner is None
        assert awareness.nation_info is None


class TestFactionQueryExceptionNarrowing:
    """Faction-related queries also narrow exceptions."""

    def test_unexpected_error_in_faction_name_propagates(self) -> None:
        player = Character(id="p1", name="Hero", location_id="road", faction_id="kingdom")
        npc = Character(id="n1", name="Guard", location_id="road", faction_id="other")
        layer = EntitiesLayer([player, npc])

        def query_fn(target: str, query: Query) -> Answer:
            if query.question == QueryType.FACTION_NAME:
                raise TypeError("unexpected bug")
            if query.question == QueryType.FACTION_RELATION:
                return Answer(value=FactionRelation.NEUTRAL)
            return Answer(value=None)

        with pytest.raises(TypeError, match="unexpected bug"):
            layer.build_nearby_entities(player, hour=12, query_fn=query_fn)

    def test_unexpected_error_in_hostility_check_propagates(self) -> None:
        player = Character(id="p1", name="Hero", location_id="road", faction_id="kingdom")
        npc = Character(id="n1", name="Guard", location_id="road", faction_id="other")
        layer = EntitiesLayer([player, npc])

        def query_fn(target: str, query: Query) -> Answer:
            if query.question == QueryType.FACTION_NAME:
                return Answer(value="Other")
            if query.question == QueryType.FACTION_RELATION:
                raise TypeError("unexpected bug in relation check")
            return Answer(value=None)

        with pytest.raises(TypeError, match="unexpected bug in relation check"):
            layer.build_nearby_entities(player, hour=12, query_fn=query_fn)
