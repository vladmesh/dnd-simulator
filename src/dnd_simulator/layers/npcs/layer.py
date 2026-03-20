"""NpcLayer — non-player characters with daily routines."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import Answer, Event, Query
from dnd_simulator.layers.npcs.models import Npc, NpcActivity, hour_in_range

if TYPE_CHECKING:
    from dnd_simulator.core.models import TimeDelta
    from dnd_simulator.core.world import WorldState


class NpcLayer(Layer):
    """NPC simulation: schedules, activities, presence in the world."""

    def __init__(self, npcs: list[Npc] | None = None) -> None:
        self._npcs: dict[str, Npc] = {}
        if npcs:
            for npc in npcs:
                self._npcs[npc.id] = npc

    @property
    def name(self) -> str:
        return "npcs"

    @property
    def tick_interval(self) -> int:
        return 0  # tick every advance_time call

    def tick(self, delta: TimeDelta, world_state: WorldState) -> list[Event]:
        """Update NPC activities based on time of day."""
        hour = world_state.time.hour
        for npc in self._npcs.values():
            self._update_activity(npc, hour)
        return []

    def _update_activity(self, npc: Npc, hour: int) -> None:
        """Set NPC activity and location based on schedule."""
        for entry in npc.schedule:
            if hour_in_range(hour, entry.start_hour, entry.end_hour):
                npc.activity = entry.activity
                npc.location_label = entry.location_label
                return
        npc.activity = NpcActivity.IDLE
        npc.location_label = "wandering"

    def handle_event(self, event: Event) -> list[Event]:
        """NPCs don't react to world events yet."""
        return []

    def query(self, query: Query) -> Answer:
        """Answer queries about NPCs.

        Supported queries:
        - "npcs_in_region": params={region_id} -> NPCs present in a region
        - "npc_info": params={npc_id} -> full NPC data
        """
        q = query.question
        params = query.params

        if q == "npcs_in_region":
            region_id = params["region_id"]
            result = []
            for npc in self._npcs.values():
                if npc.region_id == region_id:
                    result.append(
                        {
                            "id": npc.id,
                            "name": npc.name,
                            "role": npc.role,
                            "activity": npc.activity.value,
                            "location_label": npc.location_label,
                        }
                    )
            return Answer(value=result)

        if q == "npc_info":
            npc = self._npcs[params["npc_id"]]
            return Answer(
                value={
                    "id": npc.id,
                    "name": npc.name,
                    "role": npc.role,
                    "personality": npc.personality,
                    "region_id": npc.region_id,
                    "settlement_id": npc.settlement_id,
                    "activity": npc.activity.value,
                    "location_label": npc.location_label,
                    "conversation_summary": npc.conversation_summary,
                },
            )

        raise ValueError(f"Unknown npcs query: {q}")

    def get_state(self) -> dict[str, object]:
        """Serialize NPC state."""
        npcs: dict[str, Any] = {}
        for nid, npc in self._npcs.items():
            npcs[nid] = {
                "id": npc.id,
                "name": npc.name,
                "region_id": npc.region_id,
                "role": npc.role,
                "personality": npc.personality,
                "settlement_id": npc.settlement_id,
                "activity": npc.activity.value,
                "location_label": npc.location_label,
                "conversation_summary": npc.conversation_summary,
            }
        return {"npcs": npcs}

    def load_state(self, state: dict[str, object]) -> None:
        """Restore NPC state (activity, location, conversation memory)."""
        npcs_data = state["npcs"]
        assert isinstance(npcs_data, dict)

        for nid, ndata in npcs_data.items():
            assert isinstance(ndata, dict)
            npc = self._npcs.get(str(nid))
            if npc:
                npc.activity = NpcActivity(str(ndata.get("activity", "idle")))
                npc.location_label = str(ndata.get("location_label", "home"))
                npc.conversation_summary = str(ndata.get("conversation_summary", ""))
