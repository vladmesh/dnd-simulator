from __future__ import annotations

from dnd_simulator.core.models import Query, QueryType
from dnd_simulator.service.base import GameServiceProtocol


class WorldStateCommands(GameServiceProtocol):
    """Mixin: god-mode world state aggregation across all layers."""

    def get_world_state(self, session_id: str) -> dict[str, object]:
        """Build a full world-state snapshot by querying all layers."""
        session = self._get_session(session_id)
        world = session.world

        # Regions + weather
        regions_answer = world.query_layer("geography", Query(question=QueryType.REGIONS, params={}))
        assert isinstance(regions_answer.value, list)
        region_list: list[dict[str, object]] = []
        for rid in regions_answer.value:
            info = world.query_layer("geography", Query(question=QueryType.REGION_INFO, params={"region_id": rid}))
            weather = world.query_layer("geography", Query(question=QueryType.WEATHER, params={"region_id": rid}))
            assert isinstance(info.value, dict) and isinstance(weather.value, dict)
            region_list.append({**info.value, "weather": weather.value})

        # Nations
        nations_answer = world.query_layer("politics", Query(question=QueryType.NATIONS, params={}))
        assert isinstance(nations_answer.value, list)
        nation_list: list[dict[str, object]] = []
        for nid in nations_answer.value:
            info = world.query_layer("politics", Query(question=QueryType.NATION_INFO, params={"nation_id": nid}))
            assert isinstance(info.value, dict)
            nation_list.append(info.value)

        # Settlements (per region)
        all_settlements: list[dict[str, object]] = []
        for rid in regions_answer.value:
            answer = world.query_layer(
                "settlements", Query(question=QueryType.REGION_SETTLEMENTS, params={"region_id": rid})
            )
            assert isinstance(answer.value, list)
            all_settlements.extend(answer.value)

        # Entities
        entities_answer = world.query_layer("entities", Query(question=QueryType.ALL_ENTITIES, params={}))
        assert isinstance(entities_answer.value, list)

        t = world.time
        return {
            "session_id": session.session_id,
            "time": f"Y{t.year} M{t.month} D{t.day} {t.hour:02d}:{t.minute:02d}",
            "regions": region_list,
            "nations": nation_list,
            "settlements": all_settlements,
            "entities": entities_answer.value,
        }
