"""EntitiesLayer — all tracked creatures: player, NPCs, named monsters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.character import Entity
from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import Answer, Event, Query
from dnd_simulator.layers.entities.models import Npc, NpcActivity

if TYPE_CHECKING:
    from dnd_simulator.core.models import TimeDelta
    from dnd_simulator.core.world import WorldState


class EntitiesLayer(Layer):
    """All tracked entities: player, NPCs, named creatures."""

    def __init__(self, entities: list[Entity] | None = None) -> None:
        self._entities: dict[str, Entity] = {}
        if entities:
            for e in entities:
                self._entities[e.id] = e

    @property
    def name(self) -> str:
        return "entities"

    @property
    def tick_interval(self) -> int:
        return 0  # tick every advance_time call

    # -- Direct access (not through query) --

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID. Returns direct reference."""
        return self._entities.get(entity_id)

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to the layer."""
        self._entities[entity.id] = entity

    def remove_entity(self, entity_id: str) -> None:
        """Remove an entity from the layer."""
        self._entities.pop(entity_id, None)

    # -- Layer interface --

    def tick(self, delta: TimeDelta, world_state: WorldState) -> list[Event]:
        """Update all active entities."""
        hour = world_state.time.hour
        for entity in self._entities.values():
            if entity.active:
                entity.on_tick(hour)
        return []

    def handle_event(self, event: Event) -> list[Event]:
        """React to world events."""
        return []

    def query(self, query: Query) -> Answer:
        """Answer queries about entities.

        Supported queries:
        - "entities_in_region": params={region_id} -> entities in a region
        - "entity_info": params={entity_id} -> full entity data
        """
        q = query.question
        params = query.params

        if q == "entities_in_region":
            region_id = params["region_id"]
            result = []
            for e in self._entities.values():
                if e.region_id == region_id:
                    result.append(self._entity_summary(e))
            return Answer(value=result)

        if q == "entity_info":
            e = self._entities[params["entity_id"]]
            return Answer(value=self._entity_detail(e))

        raise ValueError(f"Unknown entities query: {q}")

    def _entity_summary(self, entity: Entity) -> dict[str, object]:
        """Short summary for listings."""
        base: dict[str, object] = {
            "id": entity.id,
            "name": entity.name,
        }
        if isinstance(entity, Npc):
            base["role"] = entity.role
            base["activity"] = entity.activity.value
            base["location_label"] = entity.location_label
        return base

    def _entity_detail(self, entity: Entity) -> dict[str, object]:
        """Full detail for a single entity."""
        base: dict[str, object] = {
            "id": entity.id,
            "name": entity.name,
            "region_id": entity.region_id,
            "active": entity.active,
        }
        if isinstance(entity, Npc):
            base.update(
                {
                    "role": entity.role,
                    "personality": entity.personality,
                    "settlement_id": entity.settlement_id,
                    "activity": entity.activity.value,
                    "location_label": entity.location_label,
                    "conversation_summary": entity.conversation_summary,
                }
            )
        return base

    def get_state(self) -> dict[str, object]:
        """Serialize entities state."""
        entities: dict[str, Any] = {}
        for eid, e in self._entities.items():
            data: dict[str, Any] = {
                "id": e.id,
                "name": e.name,
                "region_id": e.region_id,
                "active": e.active,
            }
            if isinstance(e, Npc):
                data.update(
                    {
                        "role": e.role,
                        "personality": e.personality,
                        "settlement_id": e.settlement_id,
                        "activity": e.activity.value,
                        "location_label": e.location_label,
                        "conversation_summary": e.conversation_summary,
                    }
                )
            entities[eid] = data
        return {"entities": entities}

    def load_state(self, state: dict[str, object]) -> None:
        """Restore mutable entity state from saved data."""
        entities_data = state["entities"]
        assert isinstance(entities_data, dict)

        for eid, edata in entities_data.items():
            assert isinstance(edata, dict)
            entity = self._entities.get(str(eid))
            if entity:
                entity.active = bool(edata.get("active", True))
                if isinstance(entity, Npc):
                    entity.activity = NpcActivity(str(edata.get("activity", "idle")))
                    entity.location_label = str(edata.get("location_label", "home"))
                    entity.conversation_summary = str(edata.get("conversation_summary", ""))
