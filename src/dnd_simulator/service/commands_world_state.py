from __future__ import annotations

import dataclasses

from dnd_simulator.core.queries import (
    query_all_entities,
    query_nation_info,
    query_nations,
    query_region_info,
    query_region_settlements,
    query_regions,
    query_weather,
)
from dnd_simulator.service.base import GameServiceProtocol


class WorldStateCommands(GameServiceProtocol):
    """Mixin: god-mode world state aggregation across all layers."""

    def get_world_state(self, session_id: str) -> dict[str, object]:
        """Build a full world-state snapshot by querying all layers."""
        session = self._get_session(session_id)
        query_fn = session.world.query_layer

        # Regions + weather
        region_ids = query_regions(query_fn)
        region_list: list[dict[str, object]] = []
        for rid in region_ids:
            info = query_region_info(query_fn, region_id=rid)
            weather = query_weather(query_fn, region_id=rid)
            region_list.append({**dataclasses.asdict(info), "weather": dataclasses.asdict(weather)})

        # Nations
        nation_list: list[dict[str, object]] = []
        for nid in query_nations(query_fn):
            nation = dataclasses.asdict(query_nation_info(query_fn, nation_id=nid))
            nation["regions"] = list(nation["regions"])
            nation_list.append(nation)

        # Settlements (per region)
        all_settlements: list[dict[str, object]] = []
        for rid in region_ids:
            all_settlements.extend(dataclasses.asdict(s) for s in query_region_settlements(query_fn, region_id=rid))

        # Entities
        entities = query_all_entities(query_fn)

        t = session.world.time
        return {
            "session_id": session.session_id,
            "time": f"Y{t.year} M{t.month} D{t.day} {t.hour:02d}:{t.minute:02d}",
            "regions": region_list,
            "nations": nation_list,
            "settlements": all_settlements,
            "entities": entities,
        }
