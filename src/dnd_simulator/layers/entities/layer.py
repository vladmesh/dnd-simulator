"""EntitiesLayer — all tracked creatures: player, NPCs, named monsters."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import structlog

from dnd_simulator.core.awareness import (
    CombatAwareness,
    EquippedInfo,
    ItemInfo,
    MerchantInfo,
    NearbyEntity,
    PeacefulAwareness,
    PerceivedEvent,
)
from dnd_simulator.core.brain import BrainType
from dnd_simulator.core.character import Character, Creature, Entity
from dnd_simulator.core.combat import BattleMap, CombatState
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.container import Container
from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, EntityKind, Event, EventType, Query
from dnd_simulator.core.monster import EncounterEntry, MonsterTemplate
from dnd_simulator.core.npc_memory import NpcMemory
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.layers.common.rng_state import dump_rng_state, load_rng_state
from dnd_simulator.layers.entities.activation_manager import ActivationManager
from dnd_simulator.layers.entities.awareness_builder import AwarenessBuilder, active_merchants_at
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.layers.entities.perception import perceive_event
from dnd_simulator.layers.entities.query_handler import QueryHandler
from dnd_simulator.layers.entities.save_models import EntitiesState

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
    EventType.ENTITY_ACTION_SURGE,
    EventType.ENTITY_LAY_ON_HANDS,
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
        seed: int | None = None,
        dice_rng: random.Random | None = None,
    ) -> None:
        self._entities: dict[str, Entity] = {}
        self._location_log: dict[str, list[Event]] = defaultdict(list)
        self._summarizer = summarizer
        self._monster_templates = monster_templates or {}
        self._encounter_tables = encounter_tables or {}
        self._encounter_cooldowns: dict[str, int] = {}  # location_id → last spawn time (seconds)
        self._creature_locations: dict[str, str] = {}  # creature_id → last known location_id
        self._spawn_counter = 0
        self._rng = random.Random(seed)
        # Materialization tracking: squad_id → (creature_ids, original_strength, spawn_count)
        self._materialized_squads: dict[str, tuple[list[str], int, int]] = {}
        # Lair materialization tracking: lair_id -> (creature_ids, core_creature_id, minion_templates)
        self._materialized_lairs: dict[str, tuple[list[str], str | None, list[str]]] = {}
        if entities:
            for e in entities:
                self._entities[e.id] = e
        self._combat = CombatManager(self._entities, self._location_log, battle_map_configs, rng=dice_rng)
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
            self._materialized_lairs,
            self._rng,
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
        return active_merchants_at(self._entities, location_id, hour)

    def get_nearest_wake_time(self) -> int | None:
        """Return the minimum intent wake time across all creatures, or None."""
        wake_times = [
            e.current_intent.wake_at_seconds
            for e in self._entities.values()
            if isinstance(e, Creature) and e.current_intent is not None
        ]
        return min(wake_times) if wake_times else None

    def update_activation(
        self,
        time: GameDateTime,
        query_fn: QueryFn | None = None,
        emit_fn: EmitFn | None = None,
    ) -> None:
        """Activate creatures near awake anchors, dormify the rest."""
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

    def build_available_items(self, creature: Creature) -> list[ItemInfo]:
        """Build the creature's available-items list for awareness."""
        return self._awareness.build_available_items(creature)

    def build_equipped(self, creature: Creature) -> list[EquippedInfo]:
        """Build the creature's equipped-items list for awareness."""
        return self._awareness.build_equipped(creature)

    def compute_reachable(
        self, creature: Creature, combat_state: CombatState | None, budget: TurnBudget
    ) -> frozenset[tuple[int, int]]:
        """Compute reachable battle-map cells for the current turn-taker."""
        return self._awareness.compute_reachable(creature, combat_state, budget)

    def build_merchants(self, creature: Creature, hour: int) -> list[MerchantInfo]:
        """Build merchant info for merchant NPCs at the creature's location."""
        return self._awareness.build_merchants(creature, hour)

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
        from dnd_simulator.layers.entities.entity_serialization import serialize_entity

        entities: dict[str, Any] = {eid: serialize_entity(e) for eid, e in self._entities.items()}
        combats = self._combat.get_combats_state()
        state = EntitiesState.model_validate(
            {"entities": entities, "combats": combats, "rng_state": dump_rng_state(self._rng)}
        )
        return state.model_dump(mode="json", by_alias=True)

    def load_state(self, state: dict[str, object]) -> None:
        """Restore mutable entity state from saved data."""
        from dnd_simulator.content_loader import parse_player
        from dnd_simulator.content_loader.items import EQUIPMENT_FIELDS, deserialize_item

        save_state = EntitiesState.model_validate(state)
        load_rng_state(self._rng, save_state.rng_state)
        state_data = save_state.model_dump(mode="json", by_alias=True)
        entities_data = save_state.entities

        for eid, esave in entities_data.items():
            edata = esave.model_dump(mode="json", by_alias=True)
            entity = self._entities.get(str(eid))

            # Recreate missing entities from save data (spawned at runtime or player)
            if entity is None:
                entity_kind = EntityKind(edata["entity_type"])
                if entity_kind is EntityKind.PLAYER:
                    entity = parse_player(edata)
                    entity.current_hp = int(edata.get("current_hp", entity.max_hp))
                    self.add_entity(entity)
                    # Fall through to restore equipment and other mutable state
                elif entity_kind is EntityKind.NPC:
                    from dnd_simulator.content_loader import parse_npc

                    entity = parse_npc(str(eid), edata)
                    self.add_entity(entity)
                    # Fall through to mutable state restoration below
                elif entity_kind is EntityKind.CREATURE:
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
                elif entity_kind is EntityKind.CONTAINER:
                    entity = Container(
                        id=str(eid),
                        name=str(edata["name"]),
                        location_id=str(edata["location_id"]),
                    )
                    self.add_entity(entity)
                    # Fall through to mutable state restoration below
                else:
                    raise ValueError(f"Cannot reconstruct entity '{eid}' from save: {entity_kind} not supported here")

            if entity:
                entity.active = bool(edata.get("active", True))
                entity.temporary = bool(edata.get("temporary", entity.temporary))
                entity.faction_id = str(edata.get("faction_id", entity.faction_id))
                loc = edata.get("location_id") or edata.get("region_id")
                if loc:
                    entity.location_id = str(loc)
                if isinstance(entity, Creature):
                    entity.in_combat = bool(edata.get("in_combat", entity.in_combat))
                    entity.is_dodging = bool(edata.get("is_dodging", entity.is_dodging))
                    entity.is_disengaging = bool(edata.get("is_disengaging", entity.is_disengaging))
                    budget_raw = edata.get("turn_budget")
                    if isinstance(budget_raw, dict):
                        entity.turn_budget = TurnBudget(
                            actions=int(budget_raw["actions"]),
                            bonus_actions=int(budget_raw["bonus_actions"]),
                            movement_remaining=int(budget_raw["movement_remaining"]),
                            reaction=int(budget_raw["reaction"]),
                        )
                    elif budget_raw is None:
                        entity.turn_budget = None
                    from dnd_simulator.core.intent import IntentType, TimedIntent

                    entity.is_anchor = bool(edata.get("is_anchor", entity.is_anchor))
                    intent_raw = edata.get("current_intent")
                    if isinstance(intent_raw, dict):
                        entity.current_intent = TimedIntent(
                            kind=IntentType(str(intent_raw["kind"])),
                            started_at_seconds=int(intent_raw["started_at_seconds"]),
                            wake_at_seconds=int(intent_raw["wake_at_seconds"]),
                        )
                    else:
                        entity.current_intent = None
                    position_raw = edata.get("combat_position")
                    if isinstance(position_raw, list | tuple) and len(position_raw) == 2:
                        entity.combat_position = (int(position_raw[0]), int(position_raw[1]))
                    else:
                        entity.combat_position = None
                    squad_id = edata.get("squad_id")
                    entity.squad_id = str(squad_id) if squad_id else None
                    entity.xp_value = int(edata.get("xp_value", entity.xp_value))
                    entity.gold = int(edata.get("gold", entity.gold))
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
                        entity.inventory = [deserialize_item(d) for d in inv_raw]
                    for field_name in EQUIPMENT_FIELDS:
                        eq_data = edata.get(field_name)
                        if isinstance(eq_data, dict):
                            setattr(entity, field_name, deserialize_item(eq_data))
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
                    rep_raw = edata.get("reputation")
                    if isinstance(rep_raw, dict):
                        entity.reputation = {str(k): int(v) for k, v in rep_raw.items()}
                if isinstance(entity, PlayerCharacter):
                    entity.current_hp = int(edata.get("current_hp", entity.current_hp))
                    entity.gold = int(edata.get("gold", entity.gold))
                    entity.experience = int(edata.get("experience", entity.experience))
                    entity.level_up_available = bool(edata.get("level_up_available", entity.level_up_available))
                elif isinstance(entity, Npc):
                    entity.current_hp = int(edata.get("current_hp", entity.current_hp))
                    ai_type = edata.get("ai_type")
                    if isinstance(ai_type, str):
                        entity.ai_type = BrainType(ai_type)
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
                elif isinstance(entity, Container):
                    entity.gold = int(edata.get("gold", entity.gold))
                    entity.is_open = bool(edata.get("is_open", entity.is_open))
                    inv_raw = edata.get("inventory")
                    if isinstance(inv_raw, list):
                        entity.inventory = [deserialize_item(d) for d in inv_raw]

        self._combat.load_combats_state(state_data["combats"])
