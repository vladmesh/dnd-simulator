"""EntitiesLayer — all tracked creatures: player, NPCs, named monsters."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

import structlog

from dnd_simulator.core.awareness import (
    CombatAwareness,
    NearbyEntity,
    PeacefulAwareness,
    PerceivedEvent,
)
from dnd_simulator.core.character import Character, Creature, Entity
from dnd_simulator.core.combat import BattleMap, CombatState
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query
from dnd_simulator.core.monster import EncounterEntry, MonsterTemplate
from dnd_simulator.layers.entities.activation_manager import ActivationManager
from dnd_simulator.layers.entities.awareness_builder import AwarenessBuilder
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.layers.entities.models import Npc, NpcMemory
from dnd_simulator.layers.entities.perception import perceive_event
from dnd_simulator.layers.entities.query_handler import QueryHandler

if TYPE_CHECKING:
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn, TimeDelta
    from dnd_simulator.llm.summarizer import MemorySummarizer

logger = structlog.get_logger(domain="entity")

# Event types that get recorded in the location log
_LOGGED_EVENTS = {
    EventType.ENTITY_SAY,
    EventType.ENTITY_ATTACK,
    EventType.ENTITY_DIED,
    EventType.ENTITY_DODGE,
    EventType.ENTITY_FLEE,
    EventType.ENTITY_MOVE,
    EventType.ENTITY_DASH,
    EventType.ENTITY_DISENGAGE,
    EventType.ENTITY_USE_ITEM,
    EventType.ENTITY_BLESS,
    EventType.ENTITY_EQUIP,
    EventType.ENTITY_UNEQUIP,
    EventType.ENTITY_SECOND_WIND,
    EventType.OPPORTUNITY_ATTACK,
    EventType.COMBAT_STARTED,
    EventType.COMBAT_ENDED,
    EventType.ENCOUNTER_SPAWNED,
    EventType.SQUAD_MOVE,
    EventType.SQUAD_COMBAT,
    EventType.SQUAD_MATERIALIZED,
    EventType.SQUAD_DEMATERIALIZED,
}


class EntitiesLayer(Layer):
    """All tracked entities: player, NPCs, named creatures."""

    def __init__(
        self,
        entities: list[Entity] | None = None,
        battle_map_configs: dict[str, BattleMap] | None = None,
        summarizer: MemorySummarizer | None = None,
        monster_templates: dict[str, MonsterTemplate] | None = None,
        encounter_tables: dict[str, list[EncounterEntry]] | None = None,
    ) -> None:
        self._entities: dict[str, Entity] = {}
        self._location_log: dict[str, list[Event]] = defaultdict(list)
        self._summarizer = summarizer
        self._monster_templates = monster_templates or {}
        self._encounter_tables = encounter_tables or {}
        self._encounter_cooldowns: dict[str, int] = {}  # location_id → last spawn time (seconds)
        self._creature_locations: dict[str, str] = {}  # creature_id → last known location_id
        self._spawn_counter = 0
        # Materialization tracking: squad_id → (creature_ids, original_strength, spawn_count)
        self._materialized_squads: dict[str, tuple[list[str], int, int]] = {}
        if entities:
            for e in entities:
                self._entities[e.id] = e
        self._combat = CombatManager(self._entities, self._location_log, battle_map_configs)
        self._awareness = AwarenessBuilder(self._entities, self._location_log, self._combat)
        self._activation = ActivationManager(
            self._entities,
            self._location_log,
            self._combat,
            self._monster_templates,
            self._encounter_tables,
            self._encounter_cooldowns,
            self._creature_locations,
            self._materialized_squads,
        )
        self._query_handler = QueryHandler(
            self._entities,
            self._location_log,
            self._combat,
            self._materialized_squads,
        )

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

    def get_active_creatures(self) -> list[Creature]:
        """Get all active creatures in the world (for the main game loop)."""
        return [e for e in self._entities.values() if isinstance(e, Creature) and e.active]

    def get_merchants_at(self, location_id: str, hour: int) -> list[Npc]:
        """Return active, alive merchants at a given location."""
        return [
            e
            for e in self._entities.values()
            if isinstance(e, Npc)
            and e.is_merchant
            and e.current_location(hour) == location_id
            and e.active
            and e.is_alive
        ]

    def get_nearest_wake_time(self) -> int | None:
        """Return the minimum wake_at_seconds across all creatures, or None."""
        wake_times = [
            e.wake_at_seconds
            for e in self._entities.values()
            if isinstance(e, Creature) and e.wake_at_seconds is not None
        ]
        return min(wake_times) if wake_times else None

    def update_activation(
        self,
        time: GameDateTime,
        query_fn: QueryFn | None = None,
        emit_fn: EmitFn | None = None,
    ) -> None:
        """Activate creatures near players, dormify the rest."""
        self._activation.update_activation(time, query_fn, emit_fn)

    # -- Combat (delegated to CombatManager) --

    def get_combat_locations(self) -> list[str]:
        """Return location IDs with active combats."""
        return self._combat.get_combat_locations()

    def get_combat(self, location_id: str) -> CombatState | None:
        """Get combat state for a location, or None if no active combat."""
        return self._combat.get_combat(location_id)

    def log_round_start(self, location_id: str, round_number: int) -> None:
        """Append a ROUND_START event to the location log."""
        self._location_log[location_id].append(
            Event(
                event_type=EventType.ROUND_START,
                source_layer="entities",
                data={"location_id": location_id, "round_number": round_number},
            )
        )

    def reset_combat_turn_state(self, creature_id: str) -> None:
        """Reset per-turn combat state for a creature (e.g. sneak attack availability)."""
        self._combat.reset_turn_state(creature_id)

    def end_combat_round(self, location_id: str) -> None:
        """Called by game loop at end of each combat round."""
        had_combat = self._combat.get_combat(location_id) is not None
        self._combat.end_combat_round(location_id)
        if had_combat and self._combat.get_combat(location_id) is None:
            self._on_combat_ended(location_id)

    # -- Awareness building (delegated to AwarenessBuilder) --

    def build_awareness(
        self, creature: Creature, time: GameDateTime, query_fn: QueryFn
    ) -> PeacefulAwareness | CombatAwareness:
        """Build awareness for a creature — dispatches by combat state."""
        return self._awareness.build_awareness(creature, time, query_fn)

    def build_peaceful_awareness(self, creature: Creature, time: GameDateTime, query_fn: QueryFn) -> PeacefulAwareness:
        """Build peaceful awareness using query_fn + internal data."""
        return self._awareness.build_peaceful_awareness(creature, time, query_fn)

    def build_combat_awareness(self, creature: Creature, query_fn: QueryFn | None = None) -> CombatAwareness:
        """Build combat awareness using internal data + optional faction queries."""
        return self._awareness.build_combat_awareness(creature, query_fn)

    def build_nearby_entities(
        self, creature: Creature, hour: int, query_fn: QueryFn | None = None
    ) -> list[NearbyEntity]:
        """Build list of nearby entities for peaceful awareness."""
        return self._awareness.build_nearby_entities(creature, hour, query_fn)

    def get_perceived_events(self, creature: Creature) -> list[PerceivedEvent]:
        """Get new events perceived by this creature as structured data.

        Advances the creature's seen-index so the same events aren't returned twice.
        This is critical for the multi-action turn loop — without it, RuleBrain
        would see the same events every iteration and loop forever.
        """
        if not isinstance(creature, Character):
            return []
        events = self._location_log.get(creature.location_id, [])
        new_events = events[creature._last_seen_log_index :]
        creature._last_seen_log_index = len(events)
        if not new_events:
            return []
        result: list[PerceivedEvent] = []
        for e in new_events:
            if e.observer_ids is not None and creature.id not in e.observer_ids:
                continue
            desc = perceive_event(e, creature, self.get_entity)
            actor_id = e.data.get("entity_id") or e.data.get("attacker_id")
            target_id = e.data.get("target_id")
            actor_name: str | None = None
            if actor_id:
                actor_entity = self.get_entity(str(actor_id))
                if actor_entity is not None:
                    actor_name = actor_entity.name
            result.append(
                PerceivedEvent(
                    description=desc,
                    event_type=e.event_type,
                    actor_id=str(actor_id) if actor_id else None,
                    actor_name=actor_name,
                    target_id=str(target_id) if target_id else None,
                    data=dict(e.data),
                )
            )
        return result

    # -- Layer interface --

    def tick(self, delta: TimeDelta, time: GameDateTime, query_fn: QueryFn, emit_fn: EmitFn) -> list[Event]:
        """No-op: Round orchestrator manages all creature turns.

        EntitiesLayer does not drive creature actions — Round calls
        run_creature_turn directly for both combat and peaceful turns.
        """
        return []

    def handle_event(self, event: Event, query_fn: QueryFn, emit_fn: EmitFn) -> ActionResult:
        """React to world events. Resolve attacks, log relevant events."""
        if event.event_type == EventType.ENTITY_DODGE:
            return self._combat.resolve_dodge(event)

        # Attack/flee can end combat (kill/flee removes fighter, <=1 left → combat ends)
        if event.event_type in (EventType.ENTITY_ATTACK, EventType.ENTITY_FLEE):
            location_id = self._event_location(event)
            had_combat = location_id is not None and self._combat.get_combat(location_id) is not None
            if event.event_type == EventType.ENTITY_ATTACK:
                result = self._combat.resolve_attack(event, query_fn=query_fn)
            else:
                result = self._combat.resolve_flee(event)
            if had_combat and location_id and self._combat.get_combat(location_id) is None:
                self._on_combat_ended(location_id)
            return result

        if event.event_type == EventType.ENTITY_MOVE:
            if "direction" in event.data:
                # Needs resolution (from handle_move via compass direction)
                return self._combat.resolve_move(event)
            # Already-resolved move (from handle_move_to) — just log it
            location_id = self._event_location(event)
            if location_id:
                self._location_log[location_id].append(event)
            return ActionResult()

        # Clean up temporary creatures on death
        if event.event_type == EventType.ENTITY_DIED:
            entity_id = str(event.data["entity_id"])
            entity = self._entities.get(entity_id)
            if entity is not None and entity.temporary:
                self.remove_entity(entity_id)

        if event.event_type in _LOGGED_EVENTS:
            if event.event_type == EventType.SQUAD_MOVE:
                # Log at both origin and destination so observers at either location see it
                for key in ("from", "to"):
                    loc = event.data.get(key)
                    if isinstance(loc, str):
                        self._location_log[loc].append(event)
            else:
                location_id = self._event_location(event)
                if location_id:
                    self._location_log[location_id].append(event)

        return ActionResult()

    # -- Perception log (delegated to QueryHandler) --

    def get_perceived_log(self, observer: Character) -> list[str]:
        """Get ALL events at observer's location that the observer can see."""
        return self._query_handler.get_perceived_log(observer)

    def get_new_perceived_events(self, observer: Character) -> list[str]:
        """Get only events since this observer last checked that they can see."""
        return self._query_handler.get_new_perceived_events(observer)

    def get_new_raw_events(self, observer: Character) -> list[Event]:
        """Peek at raw Event objects since observer's last seen index."""
        return self._query_handler.get_new_raw_events(observer)

    def _event_location(self, event: Event) -> str | None:
        """Determine which location an event happened at."""
        for key in ("entity_id", "attacker_id"):
            eid = event.data.get(key)
            if isinstance(eid, str):
                entity = self._entities.get(eid)
                if entity:
                    return entity.location_id
        # Squad events: SQUAD_MOVE uses "to" (destination), others use "location_id"
        if event.event_type == EventType.SQUAD_MOVE:
            to = event.data.get("to")
            from_ = event.data.get("from")
            if isinstance(to, str):
                return to
            if isinstance(from_, str):
                return from_
        loc = event.data.get("location_id")
        if isinstance(loc, str):
            return loc
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
                logger.info("npc_memory_updated", entity_id=entity.id, entity_name=entity.name, trigger="combat_ended")
            except Exception:
                logger.exception("npc_memory_summarize_failed", entity_id=entity.id, entity_name=entity.name)

    # -- Query (delegated to QueryHandler) --

    def query(self, query: Query) -> Answer:
        """Answer queries about entities."""
        return self._query_handler.query(query)

    def get_state(self) -> dict[str, object]:
        """Serialize entities state."""
        from dnd_simulator.core.player import PlayerCharacter

        entities: dict[str, Any] = {}
        for eid, e in self._entities.items():
            data: dict[str, Any] = {
                "id": e.id,
                "name": e.name,
                "location_id": e.location_id,
                "active": e.active,
            }
            if isinstance(e, Creature):
                # Structural fields needed to reconstruct spawned creatures from save data
                data.update(
                    {
                        "max_hp": e.max_hp,
                        "ac": e.ac,
                        "speed": e.speed,
                        "ability_scores": e.ability_scores.to_dict(),
                    }
                )
                if e.attacks:
                    data["attacks"] = [
                        {
                            "name": a.name,
                            "ability": a.ability.value,
                            "damage": [{"dice": d.dice, "type": d.type.value} for d in a.damage],
                            "reach": a.reach,
                        }
                        for a in e.attacks
                    ]
                if e.wake_at_seconds is not None:
                    data["wake_at_seconds"] = e.wake_at_seconds
                if e.conditions:
                    data["conditions"] = {c.value: r for c, r in e.conditions.items()}
                from dnd_simulator.core.player import _EQUIPMENT_FIELDS, _serialize_item

                if e.inventory:
                    data["inventory"] = [_serialize_item(item) for item in e.inventory]
                for field_name in _EQUIPMENT_FIELDS:
                    eq_item = getattr(e, field_name)
                    if eq_item is not None:
                        data[field_name] = _serialize_item(eq_item)
                if e.resource_pools:
                    data["resource_pools"] = [
                        {
                            "id": pool.id,
                            "max_uses": pool.max_uses,
                            "current_uses": pool.current_uses,
                            "reset_on": pool.reset_on.value,
                        }
                        for pool in e.resource_pools
                    ]
            if isinstance(e, PlayerCharacter):
                data["entity_type"] = "player"
                data.update(e.to_full_save_data())
            elif isinstance(e, Npc):
                data["entity_type"] = "npc"
                data.update(
                    {
                        "current_hp": e.current_hp,
                        "role": e.role.value,
                        "personality": e.personality,
                        "settlement_id": e.settlement_id,
                        "location_override": e.location_override,
                        "memory": e.memory.to_dict(),
                        "ai_type": e.ai_type,
                        # Aliases for parse_npc compatibility (used to reconstruct spawned NPCs)
                        "hp": e.max_hp,
                        "ai": e.ai_type,
                        "start_location": e.location_id,
                        "race": e.race.value,
                        "class": e.char_class.value,
                    }
                )
            elif isinstance(e, Creature):
                data["entity_type"] = "creature"
                data["current_hp"] = e.current_hp
            entities[eid] = data
        combats = self._combat.get_combats_state()
        result: dict[str, object] = {"entities": entities}
        if combats:
            result["combats"] = combats
        return result

    def load_state(self, state: dict[str, object]) -> None:
        """Restore mutable entity state from saved data."""
        from dnd_simulator.content_loader import parse_player
        from dnd_simulator.core.player import PlayerCharacter

        entities_data = state["entities"]
        assert isinstance(entities_data, dict)

        for eid, edata in entities_data.items():
            assert isinstance(edata, dict)
            entity = self._entities.get(str(eid))

            # Recreate missing entities from save data (spawned at runtime or player)
            if entity is None:
                entity_type = edata.get("entity_type")
                if entity_type == "player":
                    player = parse_player(edata)
                    player.current_hp = int(edata.get("current_hp", player.max_hp))
                    self.add_entity(player)
                    continue
                if entity_type == "npc":
                    from dnd_simulator.content_loader import parse_npc

                    entity = parse_npc(str(eid), edata)
                    self.add_entity(entity)
                    # Fall through to mutable state restoration below
                elif entity_type == "creature":
                    from dnd_simulator.content_loader import parse_ability_scores, parse_attacks

                    entity = Creature(
                        id=str(eid),
                        name=str(edata["name"]),
                        location_id=str(edata["location_id"]),
                        max_hp=int(edata["max_hp"]),
                        current_hp=int(edata["current_hp"]) if "current_hp" in edata else int(edata["max_hp"]),
                        ac=int(edata["ac"]),
                        speed=int(edata["speed"]),
                        ability_scores=parse_ability_scores(edata),
                        attacks=parse_attacks(edata.get("attacks") or []),
                    )
                    self.add_entity(entity)
                    # Fall through to mutable state restoration below
                else:
                    continue

            if entity:
                entity.active = bool(edata.get("active", True))
                loc = edata.get("location_id") or edata.get("region_id")
                if loc:
                    entity.location_id = str(loc)
                if isinstance(entity, Creature):
                    wake_at = edata.get("wake_at_seconds")
                    entity.wake_at_seconds = int(wake_at) if wake_at is not None else None
                    conditions_raw = edata.get("conditions")
                    if isinstance(conditions_raw, dict):
                        entity.conditions = {
                            Condition(str(k)): int(v) if v is not None else None for k, v in conditions_raw.items()
                        }
                    elif isinstance(conditions_raw, list):
                        # Legacy format: list of condition strings (all permanent)
                        entity.conditions = {Condition(str(c)): None for c in conditions_raw}
                    inv_raw = edata.get("inventory")
                    if isinstance(inv_raw, list):
                        from dnd_simulator.content_loader.items import deserialize_item

                        entity.inventory = [deserialize_item(d) for d in inv_raw]
                    from dnd_simulator.content_loader.items import deserialize_item as _deser
                    from dnd_simulator.core.player import _EQUIPMENT_FIELDS

                    for field_name in _EQUIPMENT_FIELDS:
                        eq_data = edata.get(field_name)
                        if isinstance(eq_data, dict):
                            setattr(entity, field_name, _deser(eq_data))
                    pools_raw = edata.get("resource_pools")
                    if isinstance(pools_raw, list):
                        from dnd_simulator.core.resource import ResourcePool, RestType

                        saved_pools = {str(d["id"]): d for d in pools_raw}
                        existing_ids = {pool.id for pool in entity.resource_pools}
                        for pool in entity.resource_pools:
                            if pool.id in saved_pools:
                                pool.current_uses = int(saved_pools[pool.id]["current_uses"])
                        for pid, pdata in saved_pools.items():
                            if pid not in existing_ids:
                                entity.resource_pools.append(
                                    ResourcePool(
                                        id=str(pdata["id"]),
                                        max_uses=int(pdata["max_uses"]),
                                        current_uses=int(pdata["current_uses"]),
                                        reset_on=RestType(str(pdata["reset_on"])),
                                    )
                                )
                if isinstance(entity, PlayerCharacter):
                    entity.current_hp = int(edata.get("current_hp", entity.current_hp))
                    entity.gold = int(edata.get("gold", entity.gold))
                elif isinstance(entity, Npc):
                    entity.current_hp = int(edata.get("current_hp", entity.current_hp))
                    ai_type = edata.get("ai_type")
                    if isinstance(ai_type, str):
                        entity.ai_type = ai_type
                    override = edata.get("location_override")
                    entity.location_override = str(override) if override else None
                    memory_data = edata.get("memory")
                    if isinstance(memory_data, dict):
                        entity.memory = NpcMemory.from_dict(memory_data)
                    else:
                        legacy = str(edata.get("conversation_summary", ""))
                        entity.memory = NpcMemory(current_conversation=legacy) if legacy else NpcMemory()
                elif isinstance(entity, Creature):
                    entity.current_hp = int(edata.get("current_hp", entity.current_hp))

        combats_data = state.get("combats")
        if isinstance(combats_data, dict):
            self._combat.load_combats_state(combats_data)
