"""Typed accessors for the inter-layer query protocol.

``Answer.value`` is ``object`` on the wire; these accessors are the single
place where each ``QueryType`` result is narrowed to its real type. Consumers
call an accessor instead of building ``Query`` objects and hand-casting the
answer. A malformed answer raises ``RuntimeError`` naming the layer and query
(fail-fast) — domain errors from layers (``KeyError``, ``ValueError``,
``LayerError``) propagate unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dnd_simulator.core.models import FactionRelation, Query, QueryType
from dnd_simulator.core.player import PlayerCharacter

if TYPE_CHECKING:
    from dnd_simulator.core.models import QueryFn

_GEOGRAPHY = "geography"
_POLITICS = "politics"
_SETTLEMENTS = "settlements"
_ENTITIES = "entities"


# ---------------------------------------------------------------------------
# Typed payloads
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeatherInfo:
    """Current weather in a region (QueryType.WEATHER)."""

    condition: str
    temperature: float


@dataclass(frozen=True)
class RegionInfo:
    """Full region data (QueryType.REGION_INFO)."""

    id: str
    name: str
    latitude: float
    longitude: float
    elevation: float
    terrain: str
    water_proximity: float
    weather: str
    temperature: float


@dataclass(frozen=True)
class LeaderInfo:
    """A nation's ruler as exposed by NATION_INFO."""

    name: str
    age: int
    trait: str


@dataclass(frozen=True)
class NationInfo:
    """Full nation data (QueryType.NATION_INFO)."""

    id: str
    name: str
    regions: tuple[str, ...]
    wealth: float
    military: float
    stability: float
    leader: LeaderInfo | None


@dataclass(frozen=True)
class SettlementInfo:
    """Full settlement data (QueryType.SETTLEMENT_INFO / REGION_SETTLEMENTS)."""

    id: str
    name: str
    region_id: str
    type: str
    population: int
    prosperity: float
    defenses: float


# ---------------------------------------------------------------------------
# Narrowing
# ---------------------------------------------------------------------------


def _expect[T](value: object, expected: type[T], *, layer: str, query: QueryType) -> T:
    if not isinstance(value, expected):
        raise RuntimeError(
            f"Malformed answer from '{layer}' layer for query {query.name}: "
            f"expected {expected.__name__}, got {type(value).__name__}"
        )
    return value


def _expect_list_of[T](value: object, item_type: type[T], *, layer: str, query: QueryType) -> list[T]:
    items = _expect(value, list, layer=layer, query=query)
    return [_expect(item, item_type, layer=layer, query=query) for item in items]


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------


def query_weather(query_fn: QueryFn, region_id: str) -> WeatherInfo:
    answer = query_fn(_GEOGRAPHY, Query(question=QueryType.WEATHER, params={"region_id": region_id}))
    return _expect(answer.value, WeatherInfo, layer=_GEOGRAPHY, query=QueryType.WEATHER)


def query_region_info(query_fn: QueryFn, region_id: str) -> RegionInfo:
    answer = query_fn(_GEOGRAPHY, Query(question=QueryType.REGION_INFO, params={"region_id": region_id}))
    return _expect(answer.value, RegionInfo, layer=_GEOGRAPHY, query=QueryType.REGION_INFO)


def query_regions(query_fn: QueryFn) -> list[str]:
    answer = query_fn(_GEOGRAPHY, Query(question=QueryType.REGIONS))
    return _expect_list_of(answer.value, str, layer=_GEOGRAPHY, query=QueryType.REGIONS)


def query_location_region(query_fn: QueryFn, location_id: str) -> str | None:
    answer = query_fn(_GEOGRAPHY, Query(question=QueryType.LOCATION_REGION, params={"location_id": location_id}))
    if answer.value is None:
        return None
    return _expect(answer.value, str, layer=_GEOGRAPHY, query=QueryType.LOCATION_REGION)


def query_is_daylight(query_fn: QueryFn, location_id: str, month: int, hour: int) -> bool:
    answer = query_fn(
        _GEOGRAPHY,
        Query(question=QueryType.IS_DAYLIGHT, params={"location_id": location_id, "month": month, "hour": hour}),
    )
    return _expect(answer.value, bool, layer=_GEOGRAPHY, query=QueryType.IS_DAYLIGHT)


# ---------------------------------------------------------------------------
# Politics
# ---------------------------------------------------------------------------


def query_nations(query_fn: QueryFn) -> list[str]:
    answer = query_fn(_POLITICS, Query(question=QueryType.NATIONS))
    return _expect_list_of(answer.value, str, layer=_POLITICS, query=QueryType.NATIONS)


def query_nation_info(query_fn: QueryFn, nation_id: str) -> NationInfo:
    answer = query_fn(_POLITICS, Query(question=QueryType.NATION_INFO, params={"nation_id": nation_id}))
    return _expect(answer.value, NationInfo, layer=_POLITICS, query=QueryType.NATION_INFO)


def query_region_owner(query_fn: QueryFn, region_id: str) -> str | None:
    answer = query_fn(_POLITICS, Query(question=QueryType.REGION_OWNER, params={"region_id": region_id}))
    if answer.value is None:
        return None
    return _expect(answer.value, str, layer=_POLITICS, query=QueryType.REGION_OWNER)


def query_faction_relation(query_fn: QueryFn, faction_a: str, faction_b: str) -> FactionRelation:
    answer = query_fn(_POLITICS, Query(question=QueryType.FACTION_RELATION, params={"a": faction_a, "b": faction_b}))
    return _expect(answer.value, FactionRelation, layer=_POLITICS, query=QueryType.FACTION_RELATION)


def query_faction_name(query_fn: QueryFn, faction_id: str) -> str | None:
    answer = query_fn(_POLITICS, Query(question=QueryType.FACTION_NAME, params={"faction_id": faction_id}))
    if answer.value is None:
        return None
    return _expect(answer.value, str, layer=_POLITICS, query=QueryType.FACTION_NAME)


# ---------------------------------------------------------------------------
# Settlements
# ---------------------------------------------------------------------------


def query_settlement_info(query_fn: QueryFn, settlement_id: str) -> SettlementInfo:
    answer = query_fn(_SETTLEMENTS, Query(question=QueryType.SETTLEMENT_INFO, params={"settlement_id": settlement_id}))
    return _expect(answer.value, SettlementInfo, layer=_SETTLEMENTS, query=QueryType.SETTLEMENT_INFO)


def query_region_settlements(query_fn: QueryFn, region_id: str) -> list[SettlementInfo]:
    answer = query_fn(_SETTLEMENTS, Query(question=QueryType.REGION_SETTLEMENTS, params={"region_id": region_id}))
    return _expect_list_of(answer.value, SettlementInfo, layer=_SETTLEMENTS, query=QueryType.REGION_SETTLEMENTS)


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


def query_players(query_fn: QueryFn) -> list[PlayerCharacter]:
    answer = query_fn(_ENTITIES, Query(question=QueryType.PLAYERS))
    return _expect_list_of(answer.value, PlayerCharacter, layer=_ENTITIES, query=QueryType.PLAYERS)


def query_player(query_fn: QueryFn, player_id: str) -> PlayerCharacter | None:
    answer = query_fn(_ENTITIES, Query(question=QueryType.PLAYER, params={"id": player_id}))
    if answer.value is None:
        return None
    return _expect(answer.value, PlayerCharacter, layer=_ENTITIES, query=QueryType.PLAYER)


def query_all_entities(query_fn: QueryFn) -> list[dict[str, object]]:
    answer = query_fn(_ENTITIES, Query(question=QueryType.ALL_ENTITIES))
    return _expect_list_of(answer.value, dict, layer=_ENTITIES, query=QueryType.ALL_ENTITIES)


def query_all_creatures(
    query_fn: QueryFn,
    entity_type: str | None = None,
    location_id: str | None = None,
    active: bool | None = None,
) -> list[dict[str, object]]:
    params: dict[str, object] = {}
    if entity_type:
        params["entity_type"] = entity_type
    if location_id:
        params["location_id"] = location_id
    if active is not None:
        params["active"] = active
    answer = query_fn(_ENTITIES, Query(question=QueryType.ALL_CREATURES, params=params))
    return _expect_list_of(answer.value, dict, layer=_ENTITIES, query=QueryType.ALL_CREATURES)


def query_entity_info(query_fn: QueryFn, entity_id: str) -> dict[str, object]:
    answer = query_fn(_ENTITIES, Query(question=QueryType.ENTITY_INFO, params={"entity_id": entity_id}))
    return _expect(answer.value, dict, layer=_ENTITIES, query=QueryType.ENTITY_INFO)
