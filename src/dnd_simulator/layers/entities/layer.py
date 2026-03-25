"""EntitiesLayer — all tracked creatures: player, NPCs, named monsters."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import structlog

from dnd_simulator.core.awareness import (
    CombatAwareness,
    CombatEntity,
    NearbyEntity,
    PeacefulAwareness,
    PerceivedEvent,
)
from dnd_simulator.core.character import Character, Creature, Entity
from dnd_simulator.core.combat import BattleMap, CombatState
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query, QueryType
from dnd_simulator.core.monster import EncounterEntry, MonsterTemplate
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.layers.entities.models import Npc, NpcMemory, activity_flavor
from dnd_simulator.layers.entities.perception import perceive_event
from dnd_simulator.rules.modifiers import effective_ac

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
    EventType.COMBAT_STARTED,
    EventType.COMBAT_ENDED,
    EventType.ENCOUNTER_SPAWNED,
}


class EntitiesLayer(Layer):
    """All tracked entities: player, NPCs, named creatures."""

    # Cooldown between encounter rolls at the same location (seconds of game time)
    ENCOUNTER_COOLDOWN_SECONDS = 600  # 10 minutes

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

    def update_activation(
        self,
        time: GameDateTime,
        query_fn: QueryFn | None = None,
        emit_fn: EmitFn | None = None,
    ) -> None:
        """Activate creatures near players, dormify the rest.

        Rules:
        - PlayerCharacter without wake_at is always active (anchor).
        - PlayerCharacter with wake_at is dormant (not an anchor) until timer expires.
        - Creatures at an anchor's location are active.
        - Creatures in combat are active (don't interrupt fights).
        - Creatures activated by proximity get wake_at cleared (woken early).
        - Everyone else is dormant (active=False).

        When query_fn/emit_fn are provided, also handles squad materialization:
        squads at active locations are spawned as creatures, squads no longer
        at active locations are dematerialized with strength updates.

        No-op if no players exist (e.g. in tests without PlayerCharacter).
        """
        from dnd_simulator.core.player import PlayerCharacter

        now = time.to_total_seconds()

        # First pass: expire wake_at timers, collect anchor locations
        player_locations: set[str] = set()
        has_players = False
        for e in self._entities.values():
            if not isinstance(e, PlayerCharacter):
                continue
            has_players = True
            if not e.is_alive:
                continue
            # Check wake_at expiry
            if e.wake_at_seconds is not None and now >= e.wake_at_seconds:
                e.wake_at_seconds = None
                logger.info("activation_wake_timer", entity_id=e.id)
            # Player is anchor only if not waiting
            if e.wake_at_seconds is None:
                e.active = True
                player_locations.add(e.location_id)
            else:
                e.active = False

        if not has_players:
            return

        # Snapshot active creature IDs before re-evaluation (for encounter checks)
        previously_active: set[str] = {e.id for e in self._entities.values() if isinstance(e, Creature) and e.active}

        # Second pass: activate/dormify non-player creatures
        hour = time.hour
        for e in self._entities.values():
            if not isinstance(e, Creature) or isinstance(e, PlayerCharacter):
                continue
            if not e.is_alive:
                continue

            # Expire wake_at for non-players too
            if e.wake_at_seconds is not None and now >= e.wake_at_seconds:
                e.wake_at_seconds = None
                logger.info("activation_wake_timer", entity_id=e.id)

            effective_location = e.location_id
            if isinstance(e, Npc):
                effective_location = e.current_location(hour)

            should_activate = effective_location in player_locations or e.in_combat
            e.active = should_activate

            # Move NPC to their scheduled location when activated
            if should_activate and effective_location != e.location_id:
                e.location_id = effective_location

            # Proximity wakeup: clear pending wait timer
            if should_activate and e.wake_at_seconds is not None:
                logger.info("activation_wake_proximity", entity_id=e.id)
                e.wake_at_seconds = None

        # Third pass: check for encounter spawns from creatures that were active
        self._check_encounters(now, previously_active)

        # Fourth pass: squad materialization/dematerialization
        if query_fn is not None:
            self._update_materialization(player_locations, query_fn, emit_fn)

    def _check_encounters(self, now: int, active_ids: set[str]) -> None:
        """Roll encounters for locations where any active creature just arrived.

        Uses `active_ids` (snapshot from before activation recalculation) so that
        creatures moving away from a player anchor still trigger encounters at
        their new location. Temporary creatures are excluded to prevent chain-triggering.
        """
        for e in list(self._entities.values()):
            if not isinstance(e, Creature):
                continue
            if e.id not in active_ids or e.temporary:
                continue

            prev = self._creature_locations.get(e.id)
            self._creature_locations[e.id] = e.location_id

            if e.location_id == prev:
                continue  # didn't move

            logger.info(
                "encounter_check_moved",
                entity_id=e.id,
                from_location=prev or "(new)",
                to_location=e.location_id,
                has_table=e.location_id in self._encounter_tables,
            )

            if e.location_id not in self._encounter_tables:
                continue  # no encounters here

            # Check cooldown
            last_roll = self._encounter_cooldowns.get(e.location_id, 0)
            if now - last_roll < self.ENCOUNTER_COOLDOWN_SECONDS:
                logger.info("encounter_check_cooldown", location=e.location_id, entity_id=e.id)
                continue

            self._encounter_cooldowns[e.location_id] = now
            self._roll_encounters(e.location_id)

    def _roll_encounters(self, location_id: str) -> None:
        """Roll each encounter entry for a location and spawn monsters."""
        from dnd_simulator.core.brain import RuleBrain

        entries = self._encounter_tables[location_id]
        spawned_names: list[str] = []

        logger.info("encounter_rolling", location=location_id, entries=len(entries))
        for entry in entries:
            roll = random.random()
            if roll >= entry.chance:
                logger.info(
                    "encounter_roll_miss",
                    location=location_id,
                    template=entry.template_id,
                    roll=round(roll, 3),
                    chance=entry.chance,
                )
                continue
            template = self._monster_templates[entry.template_id]
            count = random.randint(entry.count_min, entry.count_max)
            for _ in range(count):
                self._spawn_counter += 1
                instance_id = f"{template.id}_{self._spawn_counter}"
                creature = template.spawn(location_id, instance_id)
                creature.brain = RuleBrain()
                self.add_entity(creature)
                creature.active = True
                spawned_names.append(creature.name)
                logger.info("encounter_spawn", entity_id=instance_id, location=location_id)

        if spawned_names:
            event = Event(
                event_type=EventType.ENCOUNTER_SPAWNED,
                source_layer="entities",
                data={"location_id": location_id, "names": spawned_names},
            )
            self._location_log[location_id].append(event)

    # -- Squad materialization --

    def _update_materialization(
        self,
        active_locations: set[str],
        query_fn: QueryFn,
        emit_fn: EmitFn | None,
    ) -> None:
        """Materialize squads at active locations, dematerialize squads that left."""
        from dnd_simulator.core.brain import RuleBrain

        # Collect squad IDs currently at active locations
        from dnd_simulator.core.world import LayerError

        squads_at_active: dict[str, dict[str, Any]] = {}
        for loc in active_locations:
            try:
                answer = query_fn("ecology", Query(QueryType.SQUADS_AT_LOCATION, params={"location_id": loc}))
            except LayerError:
                return  # No ecology layer in this world — skip materialization
            for squad_info in answer.value:
                squads_at_active[str(squad_info["id"])] = squad_info

        # Materialize new squads
        for squad_id, info in squads_at_active.items():
            if squad_id in self._materialized_squads:
                continue  # already materialized
            self._materialize_squad(squad_id, info, RuleBrain)

        # Dematerialize squads no longer at active locations
        for squad_id in list(self._materialized_squads):
            if squad_id in squads_at_active:
                continue  # still at active location

            creature_ids, original_strength, spawn_count = self._materialized_squads[squad_id]

            # Don't dematerialize if any creatures are in combat
            any_in_combat = False
            for cid in creature_ids:
                entity = self._entities.get(cid)
                if isinstance(entity, Creature) and entity.in_combat:
                    any_in_combat = True
                    break
            if any_in_combat:
                continue

            self._dematerialize_squad(squad_id, creature_ids, original_strength, spawn_count, emit_fn)

    def _materialize_squad(
        self,
        squad_id: str,
        info: dict[str, Any],
        brain_cls: type,
    ) -> None:
        """Spawn creatures from a squad's member templates."""
        templates: list[str] = list(info["member_templates"])
        strength: int = int(info["strength"])
        max_strength: int = int(info["max_strength"])
        faction_id = str(info["faction_id"])
        location = str(info["current_location_id"])

        # Scale creature count by strength ratio
        count = max(1, round(len(templates) * strength / max_strength)) if max_strength > 0 else len(templates)
        templates_to_spawn = templates[:count]

        creature_ids: list[str] = []
        for tid in templates_to_spawn:
            template = self._monster_templates[tid]
            self._spawn_counter += 1
            instance_id = f"{tid}_{self._spawn_counter}"
            creature = template.spawn(location, instance_id)
            creature.squad_id = squad_id
            creature.faction_id = faction_id
            creature.brain = brain_cls()
            creature.active = True
            self.add_entity(creature)
            creature_ids.append(instance_id)
            logger.info("squad_materialize", squad_id=squad_id, creature_id=instance_id)

        self._materialized_squads[squad_id] = (creature_ids, strength, len(templates_to_spawn))

    def _dematerialize_squad(
        self,
        squad_id: str,
        creature_ids: list[str],
        original_strength: int,
        spawn_count: int,
        emit_fn: EmitFn | None,
    ) -> None:
        """Remove materialized creatures and update squad strength."""
        alive_count = 0
        for cid in creature_ids:
            entity = self._entities.get(cid)
            if isinstance(entity, Creature) and entity.is_alive:
                alive_count += 1

        # Proportional strength update
        new_strength = round(original_strength * alive_count / spawn_count) if spawn_count > 0 else original_strength

        # Remove creatures
        for cid in creature_ids:
            self.remove_entity(cid)

        del self._materialized_squads[squad_id]
        logger.info(
            "squad_dematerialize",
            squad_id=squad_id,
            alive=alive_count,
            spawned=spawn_count,
            new_strength=new_strength,
        )

        # Emit event so EcologyLayer updates squad strength
        if emit_fn is not None:
            emit_fn(
                Event(
                    event_type=EventType.SQUAD_DEMATERIALIZED,
                    source_layer="entities",
                    data={"squad_id": squad_id, "new_strength": new_strength},
                    description=f"Squad {squad_id} dematerialized (strength {new_strength})",
                )
            )

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

    # -- Awareness building --

    def build_awareness(
        self, creature: Creature, time: GameDateTime, query_fn: QueryFn
    ) -> PeacefulAwareness | CombatAwareness:
        """Build awareness for a creature — dispatches by combat state."""
        if creature.in_combat:
            return self.build_combat_awareness(creature, query_fn)
        return self.build_peaceful_awareness(creature, time, query_fn)

    def build_peaceful_awareness(self, creature: Creature, time: GameDateTime, query_fn: QueryFn) -> PeacefulAwareness:
        """Build peaceful awareness using query_fn + internal data."""
        location_name = creature.location_id
        region_name = creature.location_id

        # Resolve location → region (location may or may not belong to a region)
        region_id: str | None = None
        try:
            loc_answer = query_fn(
                "geography",
                Query(question=QueryType.LOCATION_REGION, params={"location_id": creature.location_id}),
            )
            if loc_answer.value and isinstance(loc_answer.value, str):
                region_id = loc_answer.value
        except Exception:
            logger.warning("region_resolve_failed", location_id=creature.location_id, exc_info=True)

        # Region-dependent data: weather, settlements, politics
        weather: dict[str, object] = {"condition": "clear", "temperature": 15}
        settlements: list[dict[str, object]] | None = None
        territory_owner: str | None = None
        nation_info: dict[str, object] | None = None

        if region_id is not None:
            try:
                region_answer = query_fn(
                    "geography", Query(question=QueryType.REGION_INFO, params={"region_id": region_id})
                )
                if region_answer.value and isinstance(region_answer.value, dict):
                    region_name = str(region_answer.value.get("name", region_name))
            except Exception:
                logger.warning("region_info_query_failed", region_id=region_id, exc_info=True)

            try:
                weather_answer = query_fn(
                    "geography", Query(question=QueryType.WEATHER, params={"region_id": region_id})
                )
                if weather_answer.value and isinstance(weather_answer.value, dict):
                    weather = dict(weather_answer.value)
            except Exception:
                logger.warning("weather_query_failed", region_id=region_id, exc_info=True)

            try:
                settlements_answer = query_fn(
                    "settlements", Query(question=QueryType.REGION_SETTLEMENTS, params={"region_id": region_id})
                )
                if settlements_answer.value:
                    settlements = list(settlements_answer.value)
            except Exception:
                logger.warning("settlements_query_failed", region_id=region_id, exc_info=True)

            try:
                owner_answer = query_fn(
                    "politics", Query(question=QueryType.REGION_OWNER, params={"region_id": region_id})
                )
                if owner_answer.value:
                    territory_owner = str(owner_answer.value)
                    nation_answer = query_fn(
                        "politics", Query(question=QueryType.NATION_INFO, params={"nation_id": territory_owner})
                    )
                    if nation_answer.value and isinstance(nation_answer.value, dict):
                        nation_info = dict(nation_answer.value)
            except Exception:
                logger.warning("politics_query_failed", region_id=region_id, exc_info=True)

        # Nearby entities (uses query_fn for faction hostility)
        nearby = self.build_nearby_entities(creature, time.hour, query_fn)

        # NPC scheduled location name
        if isinstance(creature, Npc):
            location_name = creature.current_location(time.hour)

        return PeacefulAwareness(
            hour=time.hour,
            day=time.day,
            month=time.month,
            year=time.year,
            weather=weather,
            location_name=location_name,
            region_name=region_name,
            settlements=settlements,
            territory_owner=territory_owner,
            nation_info=nation_info,
            nearby=nearby,
        )

    def build_combat_awareness(self, creature: Creature, query_fn: QueryFn | None = None) -> CombatAwareness:
        """Build combat awareness using internal data + optional faction queries."""
        from dnd_simulator.core.combat import Position
        from dnd_simulator.rules.movement import direction_label, grid_distance

        combat = self._combat.get_combat(creature.location_id)
        round_number = combat.round_number if combat else 1
        battle_map_positions: dict[str, Position] = dict(combat.battle_map.positions) if combat else {}
        my_pos = battle_map_positions.get(creature.id)

        # Build nearby list (exclude dead creatures)
        nearby: list[CombatEntity] = []
        for e in self._entities.values():
            if e.id == creature.id or not e.active or e.location_id != creature.location_id:
                continue
            if isinstance(e, Creature) and not e.is_alive:
                continue
            # Build description using perceive if observer is a Character
            desc = creature.perceive(e) if isinstance(creature, Character) and isinstance(e, Entity) else e.name
            is_wounded = isinstance(e, Creature) and e.current_hp < e.max_hp // 2
            distance_ft = 0
            direction = ""
            other_pos = battle_map_positions.get(e.id)
            if my_pos is not None and other_pos is not None:
                distance_ft = grid_distance(my_pos, other_pos)
                dx = other_pos.x - my_pos.x
                dy = other_pos.y - my_pos.y
                direction = direction_label(dx, dy)
            e_conditions = frozenset(e.conditions) if isinstance(e, Creature) else frozenset()
            is_hostile = self._check_faction_hostility(creature, e, query_fn)
            nearby.append(
                CombatEntity(
                    id=e.id,
                    description=desc,
                    is_wounded=is_wounded,
                    is_hostile=is_hostile,
                    distance_ft=distance_ft,
                    direction=direction,
                    x=other_pos.x if other_pos else 0,
                    y=other_pos.y if other_pos else 0,
                    conditions=e_conditions,
                )
            )

        from dnd_simulator.rules.modifiers import effective_ac, effective_speed
        from dnd_simulator.rules.weapons import get_weapon_attack

        weapon_attack = get_weapon_attack(creature)
        weapon_name = weapon_attack.name
        weapon_damage = str(weapon_attack.damage[0].dice) if weapon_attack.damage else "1"

        wall_descriptions: list[str] = []
        battle_map_ascii = ""
        if combat:
            wall_descriptions = combat.battle_map.describe_walls()
            battle_map_ascii = combat.battle_map.render_ascii(creature.id)

        return CombatAwareness(
            self_hp=creature.current_hp,
            self_max_hp=creature.max_hp,
            self_ac=effective_ac(creature),
            self_speed=effective_speed(creature),
            self_weapon=weapon_name,
            self_weapon_damage=weapon_damage,
            self_x=my_pos.x if my_pos else 0,
            self_y=my_pos.y if my_pos else 0,
            nearby=nearby,
            round_number=round_number,
            walls=wall_descriptions,
            battle_map_ascii=battle_map_ascii,
            self_conditions=frozenset(creature.conditions),
        )

    def build_nearby_entities(
        self, creature: Creature, hour: int, query_fn: QueryFn | None = None
    ) -> list[NearbyEntity]:
        """Build list of nearby entities for peaceful awareness."""
        result: list[NearbyEntity] = []
        creature_location = creature.location_id
        if isinstance(creature, Npc):
            creature_location = creature.current_location(hour)
        for e in self._entities.values():
            if e.id == creature.id or not e.active:
                continue
            if isinstance(e, Creature) and not e.is_alive:
                continue
            # Determine effective location
            e_location = e.location_id
            if isinstance(e, Npc):
                e_location = e.current_location(hour)
            if e_location != creature_location:
                continue
            desc = creature.perceive(e) if isinstance(creature, Character) and isinstance(e, Entity) else e.name
            is_wounded = isinstance(e, Creature) and e.current_hp < e.max_hp // 2
            is_hostile = self._check_faction_hostility(creature, e, query_fn)
            result.append(NearbyEntity(id=e.id, description=desc, is_wounded=is_wounded, is_hostile=is_hostile))
        if result:
            logger.info(
                "awareness_nearby",
                creature_id=creature.id,
                location=creature_location,
                nearby=[{"id": n.id, "hostile": n.is_hostile} for n in result],
            )
        return result

    def _check_faction_hostility(self, observer: Entity, other: Entity, query_fn: QueryFn | None) -> bool:
        """Check if two entities are hostile based on faction relations."""
        if not observer.faction_id or not other.faction_id:
            return False
        if observer.faction_id == other.faction_id:
            return False
        if query_fn is None:
            return False
        try:
            answer = query_fn(
                "politics",
                Query(question=QueryType.FACTION_RELATION, params={"a": observer.faction_id, "b": other.faction_id}),
            )
            relation = str(answer.value)
            is_hostile = relation == "hostile"
            logger.info(
                "faction_hostility_check",
                observer=observer.id,
                other=other.id,
                observer_faction=observer.faction_id,
                other_faction=other.faction_id,
                relation=relation,
                hostile=is_hostile,
            )
            return is_hostile
        except Exception:
            logger.warning(
                "faction_relation_query_failed",
                a=observer.faction_id,
                b=other.faction_id,
                exc_info=True,
            )
            return False

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
            result.append(
                PerceivedEvent(
                    description=desc,
                    event_type=e.event_type,
                    actor_id=str(actor_id) if actor_id else None,
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
                result = self._combat.resolve_attack(event)
            else:
                result = self._combat.resolve_flee(event)
            if had_combat and location_id and self._combat.get_combat(location_id) is None:
                self._on_combat_ended(location_id)
            return result

        if event.event_type == EventType.ENTITY_MOVE:
            return self._combat.resolve_move(event)

        # Clean up temporary creatures on death
        if event.event_type == EventType.ENTITY_DIED:
            entity_id = str(event.data["entity_id"])
            entity = self._entities.get(entity_id)
            if entity is not None and entity.temporary:
                self.remove_entity(entity_id)

        if event.event_type in _LOGGED_EVENTS:
            location_id = self._event_location(event)
            if location_id:
                self._location_log[location_id].append(event)

        return ActionResult()

    # -- Perception log --

    def get_perceived_log(self, observer: Character) -> list[str]:
        """Get ALL events at observer's location that the observer can see."""
        events = self._location_log.get(observer.location_id, [])
        if not events:
            return []
        return [
            perceive_event(e, observer, self.get_entity)
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
            perceive_event(e, observer, self.get_entity)
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

    # -- Query --

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
                if e.wake_at_seconds is not None:
                    data["wake_at_seconds"] = e.wake_at_seconds
                if e.conditions:
                    data["conditions"] = {c.value: r for c, r in e.conditions.items()}
                if e.inventory:
                    data["inventory"] = [
                        {"id": item.id, "name": item.name, "type": item.item_type.value, **item.params}
                        for item in e.inventory
                    ]
            if isinstance(e, PlayerCharacter):
                data["entity_type"] = "player"
                data.update(e.to_full_save_data())
            elif isinstance(e, Npc):
                data.update(
                    {
                        "role": e.role.value,
                        "personality": e.personality,
                        "settlement_id": e.settlement_id,
                        "location_override": e.location_override,
                        "memory": e.memory.to_dict(),
                    }
                )
            elif isinstance(e, Creature):
                data["current_hp"] = e.current_hp
            entities[eid] = data
        return {"entities": entities}

    def load_state(self, state: dict[str, object]) -> None:
        """Restore mutable entity state from saved data."""
        from dnd_simulator.content_loader import parse_player
        from dnd_simulator.core.player import PlayerCharacter

        entities_data = state["entities"]
        assert isinstance(entities_data, dict)

        for eid, edata in entities_data.items():
            assert isinstance(edata, dict)
            entity = self._entities.get(str(eid))

            # Recreate player if missing (e.g. world template has no player.yaml)
            if entity is None and edata.get("entity_type") == "player":
                player = parse_player(edata)
                player.current_hp = int(edata.get("current_hp", player.max_hp))
                self.add_entity(player)
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
                        from dnd_simulator.core.items import Item, ItemType

                        entity.inventory = [
                            Item(
                                id=str(d["id"]),
                                name=str(d["name"]),
                                item_type=ItemType(d["type"]),
                                params={k: v for k, v in d.items() if k not in ("id", "name", "type")},
                            )
                            for d in inv_raw
                        ]
                if isinstance(entity, PlayerCharacter):
                    entity.current_hp = int(edata.get("current_hp", entity.current_hp))
                    entity.gold = int(edata.get("gold", entity.gold))
                elif isinstance(entity, Npc):
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
