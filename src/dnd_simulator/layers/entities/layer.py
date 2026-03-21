"""EntitiesLayer — all tracked creatures: player, NPCs, named monsters."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from dnd_simulator.core.character import Character, Creature, Entity
from dnd_simulator.core.combat import BattleMap, CombatState
from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.layers.entities.models import Npc, NpcMemory, activity_flavor
from dnd_simulator.layers.entities.perception import perceive_event

if TYPE_CHECKING:
    from dnd_simulator.core.models import TimeDelta
    from dnd_simulator.core.world import WorldState
    from dnd_simulator.llm.summarizer import MemorySummarizer

logger = logging.getLogger("dnd_simulator.entities")

# Event types that get recorded in the location log
_LOGGED_EVENTS = {
    EventType.ENTITY_SAY,
    EventType.ENTITY_ATTACK,
    EventType.ENTITY_DIED,
    EventType.ENTITY_DODGE,
    EventType.ENTITY_FLEE,
    EventType.ENTITY_MOVE,
    EventType.ENTITY_DASH,
    EventType.COMBAT_STARTED,
    EventType.COMBAT_ENDED,
}


class EntitiesLayer(Layer):
    """All tracked entities: player, NPCs, named creatures."""

    def __init__(
        self,
        entities: list[Entity] | None = None,
        battle_map_configs: dict[str, BattleMap] | None = None,
        summarizer: MemorySummarizer | None = None,
    ) -> None:
        self._entities: dict[str, Entity] = {}
        self._location_log: dict[str, list[Event]] = defaultdict(list)
        self._summarizer = summarizer
        if entities:
            for e in entities:
                self._entities[e.id] = e
        self._combat = CombatManager(self._entities, self._location_log, battle_map_configs)

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

    def active_creatures_at_location(self, location_id: str, exclude_id: str = "") -> list[Creature]:
        """Get active creatures at a location (for turn polling)."""
        return [
            e
            for e in self._entities.values()
            if isinstance(e, Creature) and e.active and e.location_id == location_id and e.id != exclude_id
        ]

    def get_active_creatures(self) -> list[Creature]:
        """Get all active creatures in the world (for the main game loop)."""
        return [e for e in self._entities.values() if isinstance(e, Creature) and e.active]

    # -- Combat (delegated to CombatManager) --

    def get_combat_locations(self) -> list[str]:
        """Return location IDs with active combats."""
        return self._combat.get_combat_locations()

    def get_combat(self, location_id: str) -> CombatState | None:
        """Get combat state for a location, or None if no active combat."""
        return self._combat.get_combat(location_id)

    def end_combat_round(self, location_id: str) -> None:
        """Called by game loop at end of each combat round."""
        had_combat = self._combat.get_combat(location_id) is not None
        self._combat.end_combat_round(location_id)
        if had_combat and self._combat.get_combat(location_id) is None:
            self._on_combat_ended(location_id)

    # -- Layer interface --

    def tick(self, delta: TimeDelta, world_state: WorldState) -> list[Event]:
        """Update all active entities. Schedule is computed, not ticked."""
        return []

    def handle_event(self, event: Event) -> ActionResult:
        """React to world events. Resolve attacks, log relevant events."""
        if event.event_type == EventType.ENTITY_DODGE:
            return self._combat.resolve_dodge(event)

        # Attack/flee can end combat (kill/flee removes fighter, <=1 left → combat ends)
        if event.event_type in (EventType.ENTITY_ATTACK, EventType.ENTITY_FLEE):
            location_id = self._event_location(event)
            had_combat = location_id is not None and self._combat.get_combat(location_id) is not None
            if event.event_type == EventType.ENTITY_ATTACK:
                result = self._combat.resolve_attack(event)
            else:
                result = self._combat.resolve_flee(event)
            if had_combat and location_id and self._combat.get_combat(location_id) is None:
                self._on_combat_ended(location_id)
            return result

        if event.event_type == EventType.ENTITY_MOVE:
            return self._combat.resolve_move(event)

        if event.event_type == EventType.ENTITY_DASH:
            return self._combat.resolve_move(event, dash=True)

        if event.event_type in _LOGGED_EVENTS:
            location_id = self._event_location(event)
            if location_id:
                self._location_log[location_id].append(event)

        return ActionResult()

    # -- Perception log --

    def get_perceived_log(self, observer: Character) -> list[str]:
        """Get ALL events at observer's location that the observer can see.

        Used for NPC LLM prompts — full history as context/memory.
        Filters by observer_ids: events with observer_ids set are only visible
        to listed entities.
        """
        events = self._location_log.get(observer.location_id, [])
        if not events:
            return []
        return [
            perceive_event(e, observer, self.get_entity)
            for e in events
            if e.observer_ids is None or observer.id in e.observer_ids
        ]

    def get_new_perceived_events(self, observer: Character) -> list[str]:
        """Get only events since this observer last checked that they can see.

        Updates the observer's index. Used for player display.
        """
        events = self._location_log.get(observer.location_id, [])
        last_seen = observer._last_seen_log_index
        new_events = events[last_seen:]
        observer._last_seen_log_index = len(events)
        if not new_events:
            return []
        return [
            perceive_event(e, observer, self.get_entity)
            for e in new_events
            if e.observer_ids is None or observer.id in e.observer_ids
        ]

    def get_new_raw_events(self, observer: Character) -> list[Event]:
        """Peek at raw Event objects since observer's last seen index.

        Does NOT advance the index — safe to call alongside get_new_perceived_events.
        """
        events = self._location_log.get(observer.location_id, [])
        new_events = events[observer._last_seen_log_index :]
        if not new_events:
            return []
        return [e for e in new_events if e.observer_ids is None or observer.id in e.observer_ids]

    def _event_location(self, event: Event) -> str | None:
        """Determine which location an event happened at."""
        for key in ("entity_id", "attacker_id"):
            eid = event.data.get(key)
            if isinstance(eid, str):
                entity = self._entities.get(eid)
                if entity:
                    return entity.location_id
        return None

    def _on_combat_ended(self, location_id: str) -> None:
        """After combat ends, summarize combat events into each NPC participant's memory."""
        if not self._summarizer:
            return

        log = self._location_log.get(location_id, [])

        # Find the matching COMBAT_STARTED — scan backward from the end
        start_idx = None
        for i in range(len(log) - 1, -1, -1):
            if log[i].event_type == EventType.COMBAT_STARTED:
                start_idx = i
                break
        if start_idx is None:
            return

        combat_events = log[start_idx:]
        participant_ids: list[str] = []
        turn_order = log[start_idx].data.get("turn_order", [])
        if isinstance(turn_order, list):
            participant_ids = [str(pid) for pid in turn_order]

        for pid in participant_ids:
            entity = self._entities.get(pid)
            if not isinstance(entity, Npc):
                continue

            # Perceive combat events from this NPC's point of view
            perceived = [
                perceive_event(e, entity, self.get_entity)
                for e in combat_events
                if e.observer_ids is None or entity.id in e.observer_ids
            ]
            if not perceived:
                continue

            try:
                entity.memory = self._summarizer.summarize(entity.memory, perceived, "combat_ended")
                if self._summarizer.needs_compression(entity.memory):
                    entity.memory = self._summarizer.summarize(entity.memory, [], "recent_overflow")
                logger.info("[Summarizer] Updated memory for NPC '%s' after combat", entity.name)
            except Exception:
                logger.exception("[Summarizer] Failed to summarize combat for NPC '%s'", entity.name)

    # -- Query --

    def query(self, query: Query) -> Answer:
        """Answer queries about entities.

        Supported queries:
        - "entities_at_location": params={location_id} -> entities at a location
        - "entity_info": params={entity_id} -> full entity data
        - "all_entities": params={} -> entity_info for all active entities
        - "all_npcs": params={} -> NPC detail for all active NPCs
        - "npc_info": params={npc_id} -> single NPC detail (raises ValueError if not NPC)
        - "perceived_log": params={entity_id} -> recent events from entity's POV
        - "combat_info": params={location_id} -> combat state
        - "perceive_entity": params={observer_id, target_id} -> perception string
        """
        q = query.question
        params = query.params

        if q == "entities_at_location":
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

        if q == "entity_info":
            e = self._entities[params["entity_id"]]
            return Answer(value=self._entity_detail(e))

        if q == "all_entities":
            result = []
            for e in self._entities.values():
                if e.active:
                    result.append(self._entity_detail(e))
            return Answer(value=result)

        if q == "all_npcs":
            result = []
            for e in self._entities.values():
                if e.active and isinstance(e, Npc):
                    result.append(self._npc_detail(e))
            return Answer(value=result)

        if q == "npc_info":
            npc = self._entities.get(params["npc_id"])
            if npc is None or not isinstance(npc, Npc):
                raise ValueError(f"NPC '{params['npc_id']}' not found")
            return Answer(value=self._npc_detail(npc))

        if q == "perceived_log":
            e = self._entities[params["entity_id"]]
            if isinstance(e, Character):
                return Answer(value=self.get_perceived_log(e))
            return Answer(value=[])

        if q == "new_perceived_events":
            e = self._entities[params["entity_id"]]
            if isinstance(e, Character):
                return Answer(value=self.get_new_perceived_events(e))
            return Answer(value=[])

        if q == "new_raw_events":
            e = self._entities[params["entity_id"]]
            if isinstance(e, Character):
                return Answer(value=self.get_new_raw_events(e))
            return Answer(value=[])

        if q == "combat_info":
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

        if q == "perceive_entity":
            observer = self._entities.get(params["observer_id"])
            target = self._entities.get(params["target_id"])
            if observer and target and isinstance(observer, Character) and isinstance(target, Entity):
                return Answer(value=observer.perceive(target))
            return Answer(value=str(params["target_id"]))

        raise ValueError(f"Unknown entities query: {q}")

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
            base["role"] = entity.role
            base["activity"] = npc_activity.value
            base["activity_flavor"] = activity_flavor(entity.role, npc_activity)
            base["location_label"] = entity.current_location(hour)
        return base

    def _entity_detail(self, entity: Entity) -> dict[str, object]:
        """Full detail for a single entity."""
        base: dict[str, object] = {
            "id": entity.id,
            "name": entity.name,
            "location_id": entity.location_id,
            "active": entity.active,
        }
        if isinstance(entity, Npc):
            base.update(
                {
                    "role": entity.role,
                    "personality": entity.personality,
                    "settlement_id": entity.settlement_id,
                    "memory": entity.memory.to_dict(),
                }
            )
        return base

    def _npc_detail(self, npc: Npc) -> dict[str, object]:
        """Full NPC detail including creature stats."""
        return {
            "id": npc.id,
            "name": npc.name,
            "location_id": npc.location_id,
            "role": npc.role,
            "personality": npc.personality,
            "hp": npc.current_hp,
            "max_hp": npc.max_hp,
            "ac": npc.ac,
            "ai_type": npc.ai_type,
            "active": npc.active,
        }

    def get_state(self) -> dict[str, object]:
        """Serialize entities state."""
        entities: dict[str, Any] = {}
        for eid, e in self._entities.items():
            data: dict[str, Any] = {
                "id": e.id,
                "name": e.name,
                "location_id": e.location_id,
                "active": e.active,
            }
            if isinstance(e, Npc):
                data.update(
                    {
                        "role": e.role,
                        "personality": e.personality,
                        "settlement_id": e.settlement_id,
                        "location_override": e.location_override,
                        "memory": e.memory.to_dict(),
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
                # Backward compat: support both location_id and region_id
                loc = edata.get("location_id") or edata.get("region_id")
                if loc:
                    entity.location_id = str(loc)
                if isinstance(entity, Npc):
                    override = edata.get("location_override")
                    entity.location_override = str(override) if override else None
                    # Load memory: prefer new format, fall back to legacy conversation_summary
                    memory_data = edata.get("memory")
                    if isinstance(memory_data, dict):
                        entity.memory = NpcMemory.from_dict(memory_data)
                    else:
                        legacy = str(edata.get("conversation_summary", ""))
                        entity.memory = NpcMemory(current_conversation=legacy) if legacy else NpcMemory()
