from __future__ import annotations

from dnd_simulator.core.models import Query, QueryType
from dnd_simulator.service.base import GameServiceProtocol


def _expect[T](value: object, expected: type[T], *, layer: str, query: QueryType) -> T:
    """Narrow a layer answer to ``expected`` or fail fast with a descriptive error.

    Replaces bare ``assert isinstance`` (stripped under ``python -O``, surfaces as an
    opaque ``AssertionError``/HTTP 500) with a typed ``RuntimeError`` naming the
    offending layer and query.
    """
    if not isinstance(value, expected):
        raise RuntimeError(
            f"Malformed answer from '{layer}' layer for query {query.name}: "
            f"expected {expected.__name__}, got {type(value).__name__}"
        )
    return value


class WorldStateCommands(GameServiceProtocol):
    """Mixin: god-mode world state aggregation across all layers."""

    def get_world_state(self, session_id: str) -> dict[str, object]:
        """Build a full world-state snapshot by querying all layers."""
        session = self._get_session(session_id)
        world = session.world

        # Regions + weather
        regions_answer = world.query_layer("geography", Query(question=QueryType.REGIONS, params={}))
        region_ids = _expect(regions_answer.value, list, layer="geography", query=QueryType.REGIONS)
        region_list: list[dict[str, object]] = []
        for rid in region_ids:
            info = world.query_layer("geography", Query(question=QueryType.REGION_INFO, params={"region_id": rid}))
            weather = world.query_layer("geography", Query(question=QueryType.WEATHER, params={"region_id": rid}))
            info_val = _expect(info.value, dict, layer="geography", query=QueryType.REGION_INFO)
            weather_val = _expect(weather.value, dict, layer="geography", query=QueryType.WEATHER)
            region_list.append({**info_val, "weather": weather_val})

        # Nations
        nations_answer = world.query_layer("politics", Query(question=QueryType.NATIONS, params={}))
        nation_ids = _expect(nations_answer.value, list, layer="politics", query=QueryType.NATIONS)
        nation_list: list[dict[str, object]] = []
        for nid in nation_ids:
            info = world.query_layer("politics", Query(question=QueryType.NATION_INFO, params={"nation_id": nid}))
            nation_list.append(_expect(info.value, dict, layer="politics", query=QueryType.NATION_INFO))

        # Settlements (per region)
        all_settlements: list[dict[str, object]] = []
        for rid in region_ids:
            answer = world.query_layer(
                "settlements", Query(question=QueryType.REGION_SETTLEMENTS, params={"region_id": rid})
            )
            all_settlements.extend(_expect(answer.value, list, layer="settlements", query=QueryType.REGION_SETTLEMENTS))

        # Entities
        entities_answer = world.query_layer("entities", Query(question=QueryType.ALL_ENTITIES, params={}))
        entities = _expect(entities_answer.value, list, layer="entities", query=QueryType.ALL_ENTITIES)

        t = world.time
        return {
            "session_id": session.session_id,
            "time": f"Y{t.year} M{t.month} D{t.day} {t.hour:02d}:{t.minute:02d}",
            "regions": region_list,
            "nations": nation_list,
            "settlements": all_settlements,
            "entities": entities,
        }
