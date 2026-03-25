"""QueryHandler — query dispatch and entity detail building for EntitiesLayer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_simulator.core.character import Character, Creature, Entity
from dnd_simulator.core.models import Answer, Query, QueryType
from dnd_simulator.layers.entities.models import Npc, activity_flavor
from dnd_simulator.layers.entities.perception import perceive_event
from dnd_simulator.rules.modifiers import effective_ac

if TYPE_CHECKING:
    from dnd_simulator.core.models import Event
    from dnd_simulator.layers.entities.combat_manager import CombatManager


class QueryHandler:
    """Handles all query dispatch and entity detail building for the entities layer."""

    def __init__(
        self,
        entities: dict[str, Entity],
        location_log: dict[str, list[Event]],
        combat: CombatManager,
        materialized_squads: dict[str, tuple[list[str], int, int]],
    ) -> None:
        self._entities = entities
        self._location_log = location_log
        self._combat = combat
        self._materialized_squads = materialized_squads

    def query(self, query: Query) -> Answer:
        """Answer queries about entities."""
        q = query.question
        params = query.params

        if q is QueryType.PLAYERS:
            from dnd_simulator.core.player import PlayerCharacter

            return Answer(value=[e for e in self._entities.values() if isinstance(e, PlayerCharacter)])

        if q is QueryType.PLAYER:
            from dnd_simulator.core.player import PlayerCharacter

            pid = params.get("id")
            if pid:
                e = self._entities.get(str(pid))
                return Answer(value=e if isinstance(e, PlayerCharacter) else None)
            # Legacy: first player found
            for e in self._entities.values():
                if isinstance(e, PlayerCharacter):
                    return Answer(value=e)
            return Answer(value=None)

        if q is QueryType.ENTITIES_AT_LOCATION:
            location_id = params["location_id"]
            hour = int(params.get("hour", 12))
            result = []
            for e in self._entities.values():
                if not e.active:
                    continue
                if isinstance(e, Npc):
                    if e.current_location(hour) == location_id:
                        result.append(self._entity_summary(e, hour))
                elif e.location_id == location_id:
                    result.append(self._entity_summary(e))
            return Answer(value=result)

        if q is QueryType.ENTITY_INFO:
            e = self._entities[params["entity_id"]]
            return Answer(value=self._entity_detail(e))

        if q is QueryType.ALL_ENTITIES:
            result = []
            for e in self._entities.values():
                if e.active:
                    result.append(self._entity_detail(e))
            return Answer(value=result)

        if q is QueryType.ALL_CREATURES:
            from dnd_simulator.core.player import PlayerCharacter

            # Filterable creature list for master panel
            filter_type = params.get("entity_type")  # "player", "npc", or None for all
            filter_location = params.get("location_id")
            filter_active = params.get("active")  # True/False/None
            result = []
            for e in self._entities.values():
                if not isinstance(e, Creature):
                    continue
                if filter_active is not None and e.active != filter_active:
                    continue
                if filter_location and e.location_id != filter_location:
                    continue
                if filter_type == "player" and not isinstance(e, PlayerCharacter):
                    continue
                if filter_type == "npc" and not isinstance(e, Npc):
                    continue
                if filter_type == "monster" and (isinstance(e, (PlayerCharacter, Npc))):
                    continue
                result.append(self._entity_detail(e))
            return Answer(value=result)

        if q is QueryType.ALL_NPCS:
            result = []
            for e in self._entities.values():
                if e.active and isinstance(e, Npc):
                    result.append(self._npc_detail(e))
            return Answer(value=result)

        if q is QueryType.NPC_INFO:
            npc = self._entities.get(params["npc_id"])
            if npc is None or not isinstance(npc, Npc):
                raise ValueError(f"NPC '{params['npc_id']}' not found")
            return Answer(value=self._npc_detail(npc))

        if q is QueryType.PERCEIVED_LOG:
            e = self._entities[params["entity_id"]]
            if isinstance(e, Character):
                return Answer(value=self.get_perceived_log(e))
            return Answer(value=[])

        if q is QueryType.NEW_PERCEIVED_EVENTS:
            e = self._entities[params["entity_id"]]
            if isinstance(e, Character):
                return Answer(value=self.get_new_perceived_events(e))
            return Answer(value=[])

        if q is QueryType.NEW_RAW_EVENTS:
            e = self._entities[params["entity_id"]]
            if isinstance(e, Character):
                return Answer(value=self.get_new_raw_events(e))
            return Answer(value=[])

        if q is QueryType.COMBAT_INFO:
            location_id = params["location_id"]
            combat = self._combat.get_combat(location_id)
            if combat:
                return Answer(
                    value={
                        "round_number": combat.round_number,
                        "turn_order": combat.turn_order,
                        "positions": dict(combat.battle_map.positions),
                        "wall_descriptions": combat.battle_map.describe_walls(),
                    }
                )
            return Answer(value=None)

        if q is QueryType.PERCEIVE_ENTITY:
            observer = self._entities.get(params["observer_id"])
            target = self._entities.get(params["target_id"])
            if observer and target and isinstance(observer, Character) and isinstance(target, Entity):
                return Answer(value=observer.perceive(target))
            return Answer(value=str(params["target_id"]))

        raise ValueError(f"Unknown entities query: {q}")

    # -- Perception log --

    def get_perceived_log(self, observer: Character) -> list[str]:
        """Get ALL events at observer's location that the observer can see."""
        events = self._location_log.get(observer.location_id, [])
        if not events:
            return []
        return [
            perceive_event(e, observer, self._get_entity)
            for e in events
            if e.observer_ids is None or observer.id in e.observer_ids
        ]

    def get_new_perceived_events(self, observer: Character) -> list[str]:
        """Get only events since this observer last checked that they can see."""
        events = self._location_log.get(observer.location_id, [])
        last_seen = observer._last_seen_log_index
        new_events = events[last_seen:]
        observer._last_seen_log_index = len(events)
        if not new_events:
            return []
        return [
            perceive_event(e, observer, self._get_entity)
            for e in new_events
            if e.observer_ids is None or observer.id in e.observer_ids
        ]

    def get_new_raw_events(self, observer: Character) -> list[Event]:
        """Peek at raw Event objects since observer's last seen index."""
        events = self._location_log.get(observer.location_id, [])
        new_events = events[observer._last_seen_log_index :]
        if not new_events:
            return []
        return [e for e in new_events if e.observer_ids is None or observer.id in e.observer_ids]

    # -- Detail builders --

    def _entity_summary(self, entity: Entity, hour: int = 12) -> dict[str, object]:
        """Short summary for listings."""
        base: dict[str, object] = {
            "id": entity.id,
            "name": entity.name,
        }
        if isinstance(entity, Creature):
            base["is_wounded"] = entity.current_hp < entity.max_hp // 2
        if isinstance(entity, Npc):
            npc_activity = entity.scheduled_activity(hour)
            base["role"] = entity.role.value
            base["activity"] = npc_activity.value
            base["activity_flavor"] = activity_flavor(entity.role, npc_activity)
            base["location_label"] = entity.current_location(hour)
        return base

    def _entity_detail(self, entity: Entity) -> dict[str, object]:
        """Full detail for a single entity."""
        from dnd_simulator.core.player import PlayerCharacter

        base: dict[str, object] = {
            "id": entity.id,
            "name": entity.name,
            "location_id": entity.location_id,
            "active": entity.active,
        }
        if isinstance(entity, Creature):
            base.update(
                {
                    "hp": entity.current_hp,
                    "max_hp": entity.max_hp,
                    "ac": effective_ac(entity),
                    "conditions": sorted(c.value for c in entity.conditions),
                }
            )
        if isinstance(entity, Character):
            base.update(
                {
                    "race": entity.race.value,
                    "char_class": entity.char_class.value,
                    "level": entity.level,
                    "gold": entity.gold,
                }
            )
        if isinstance(entity, PlayerCharacter):
            base["entity_type"] = "player"
        elif isinstance(entity, Npc):
            base.update(
                {
                    "entity_type": "npc",
                    "role": entity.role.value,
                    "personality": entity.personality,
                    "settlement_id": entity.settlement_id,
                    "ai_type": entity.ai_type,
                    "memory": entity.memory.to_dict(),
                }
            )
        elif isinstance(entity, Creature):
            base["entity_type"] = "monster"
        return base

    def _npc_detail(self, npc: Npc) -> dict[str, object]:
        """Full NPC detail including creature stats."""
        return {
            "id": npc.id,
            "name": npc.name,
            "location_id": npc.location_id,
            "role": npc.role.value,
            "personality": npc.personality,
            "hp": npc.current_hp,
            "max_hp": npc.max_hp,
            "ac": effective_ac(npc),
            "ai_type": npc.ai_type,
            "active": npc.active,
        }

    def _get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID — used as callback for perceive_event."""
        return self._entities.get(entity_id)
