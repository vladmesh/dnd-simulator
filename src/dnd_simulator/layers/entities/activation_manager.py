"""Activation, encounter, and squad materialization logic for the entities layer."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import structlog

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.lair import LairState
from dnd_simulator.core.models import Event, EventType, FactionRelation, Query, QueryType
from dnd_simulator.core.monster import EncounterEntry

if TYPE_CHECKING:
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn
    from dnd_simulator.core.monster import MonsterTemplate
    from dnd_simulator.layers.entities.combat_manager import CombatManager

logger = structlog.get_logger(domain="entity")

ENCOUNTER_COOLDOWN_SECONDS = 600  # 10 minutes


class ActivationManager:
    """Manages proximity-based activation, encounter spawns, and squad materialization.

    Operates on shared entity and state references owned by EntitiesLayer.
    """

    def __init__(
        self,
        entities: dict[str, Entity],
        location_log: dict[str, list[Event]],
        combat: CombatManager,
        monster_templates: dict[str, MonsterTemplate],
        encounter_tables: dict[str, list[EncounterEntry]],
        encounter_cooldowns: dict[str, int],
        creature_locations: dict[str, str],
        materialized_squads: dict[str, tuple[list[str], int, int]],
        materialized_lairs: dict[str, tuple[list[str], str | None, list[str]]],
    ) -> None:
        self._entities = entities
        self._location_log = location_log
        self._combat = combat
        self._monster_templates = monster_templates
        self._encounter_tables = encounter_tables
        self._encounter_cooldowns = encounter_cooldowns
        self._creature_locations = creature_locations
        self._materialized_squads = materialized_squads
        self._materialized_lairs = materialized_lairs
        self._spawn_counter = 0

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
        from dnd_simulator.layers.entities.models import Npc

        now = time.to_total_seconds()

        # First pass: expire wake_at timers, collect anchor locations
        player_locations: set[str] = set()
        has_players = False
        for e in self._entities.values():
            if not isinstance(e, PlayerCharacter):
                continue
            has_players = True
            if not e.is_alive:
                e.active = False
                e.wake_at_seconds = None
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
                e.active = False
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
        self._check_encounters(now, previously_active, query_fn)

        # Fourth pass: squad + lair materialization/dematerialization
        if query_fn is not None:
            self._update_materialization(player_locations, query_fn, emit_fn)
            self._update_lair_materialization(now, player_locations, query_fn, emit_fn)

    def _check_encounters(self, now: int, active_ids: set[str], query_fn: QueryFn | None = None) -> None:
        """Roll encounters for locations where any active creature just arrived."""
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
            if now - last_roll < ENCOUNTER_COOLDOWN_SECONDS:
                logger.info("encounter_check_cooldown", location=e.location_id, entity_id=e.id)
                continue

            self._encounter_cooldowns[e.location_id] = now
            self._roll_encounters(e.location_id, query_fn)

    def _roll_encounters(self, location_id: str, query_fn: QueryFn | None = None) -> None:
        """Roll each encounter entry for a location and spawn monsters."""
        from dnd_simulator.rules.rule_brain import RuleBrain

        entries = self._encounter_tables[location_id]
        spawned_names: list[str] = []
        spawned_creatures: list[Creature] = []

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
                self._entities[creature.id] = creature
                creature.active = True
                spawned_names.append(creature.name)
                spawned_creatures.append(creature)
                logger.info("encounter_spawn", entity_id=instance_id, location=location_id)

        if spawned_names:
            event = Event(
                event_type=EventType.ENCOUNTER_SPAWNED,
                source_layer="entities",
                data={"location_id": location_id, "names": spawned_names},
            )
            self._location_log[location_id].append(event)

            # Auto-start combat if spawned creatures are hostile to anyone at this location
            if query_fn is not None and location_id not in self._combat.get_combat_locations():
                self._maybe_start_combat(location_id, spawned_creatures, query_fn)

    def _maybe_start_combat(self, location_id: str, spawned: list[Creature], query_fn: QueryFn) -> None:
        """Start combat if any spawned creature is hostile to an existing creature at the location."""
        existing = [
            e
            for e in self._entities.values()
            if isinstance(e, Creature) and e.location_id == location_id and e.is_alive and e not in spawned
        ]
        for sc in spawned:
            if not sc.faction_id:
                continue
            for ex in existing:
                if not ex.faction_id:
                    continue
                try:
                    answer = query_fn(
                        "politics",
                        Query(question=QueryType.FACTION_RELATION, params={"a": sc.faction_id, "b": ex.faction_id}),
                    )
                    if answer.value == FactionRelation.HOSTILE:
                        logger.info(
                            "encounter_auto_combat",
                            location=location_id,
                            spawned_faction=sc.faction_id,
                            existing_faction=ex.faction_id,
                        )
                        self._combat.start_combat(location_id)
                        return
                except Exception:
                    pass

    # -- Squad materialization --

    def _update_materialization(
        self,
        active_locations: set[str],
        query_fn: QueryFn,
        emit_fn: EmitFn | None,
    ) -> None:
        """Materialize squads at active locations, dematerialize squads that left."""
        from dnd_simulator.core.world import LayerError
        from dnd_simulator.rules.rule_brain import RuleBrain

        squads_at_active: dict[str, dict[str, Any]] = {}
        for loc in active_locations:
            try:
                answer = query_fn("ecology", Query(QueryType.SQUADS_AT_LOCATION, params={"location_id": loc}))
            except LayerError:
                return  # No ecology layer in this world — skip materialization
            assert isinstance(answer.value, list)
            for squad_info in answer.value:
                squads_at_active[str(squad_info["id"])] = squad_info

        # Materialize new squads
        for squad_id, info in squads_at_active.items():
            if squad_id in self._materialized_squads:
                continue  # already materialized
            self._materialize_squad(squad_id, info, RuleBrain)
            # Auto-start combat if materialized creatures are hostile to someone here
            location_id = str(info["current_location_id"])
            creature_ids = self._materialized_squads[squad_id][0]
            spawned = [
                e for cid in creature_ids if cid in self._entities and isinstance((e := self._entities[cid]), Creature)
            ]
            if spawned and location_id not in self._combat.get_combat_locations():
                self._maybe_start_combat(location_id, spawned, query_fn)

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
            self._entities[creature.id] = creature
            creature_ids.append(instance_id)
            logger.info("squad_materialize", squad_id=squad_id, creature_id=instance_id)

        self._materialized_squads[squad_id] = (creature_ids, strength, len(templates_to_spawn))

        # Log materialization event so players at this location see it
        squad_name = str(info.get("name", squad_id))
        mat_event = Event(
            event_type=EventType.SQUAD_MATERIALIZED,
            source_layer="entities",
            data={
                "squad_id": squad_id,
                "squad_name": squad_name,
                "location_id": location,
                "creature_count": len(creature_ids),
            },
            description=f"{squad_name} materialized at {location}",
        )
        self._location_log[location].append(mat_event)

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
        location_id: str | None = None
        squad_name = squad_id
        for cid in creature_ids:
            entity = self._entities.get(cid)
            if isinstance(entity, Creature):
                if location_id is None:
                    location_id = entity.location_id
                    squad_name = entity.name  # creatures share the template name
                if entity.is_alive:
                    alive_count += 1

        # Proportional strength update
        new_strength = round(original_strength * alive_count / spawn_count) if spawn_count > 0 else original_strength

        # Remove creatures
        for cid in creature_ids:
            self._entities.pop(cid, None)

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
                    data={
                        "squad_id": squad_id,
                        "squad_name": squad_name,
                        "location_id": location_id or "",
                        "new_strength": new_strength,
                    },
                    description=f"Squad {squad_id} dematerialized (strength {new_strength})",
                )
            )

    # -- Lair materialization --

    def _update_lair_materialization(
        self,
        now: int,
        active_locations: set[str],
        query_fn: QueryFn,
        emit_fn: EmitFn | None,
    ) -> None:
        """Materialize active lairs at active locations; dematerialize lairs the player left."""
        from dnd_simulator.core.world import LayerError

        lairs_at_active: dict[str, dict[str, Any]] = {}
        for loc in active_locations:
            try:
                answer = query_fn("ecology", Query(QueryType.LAIRS_AT_LOCATION, params={"location_id": loc}))
            except LayerError:
                return  # No ecology layer in this world — skip lair materialization
            assert isinstance(answer.value, list)
            for lair_info in answer.value:
                lairs_at_active[str(lair_info["id"])] = lair_info

        # Materialize new lairs (skip depleted — terminal, nothing spawns)
        for lair_id, info in lairs_at_active.items():
            if lair_id in self._materialized_lairs:
                continue
            if info["state"] != LairState.ACTIVE.value:
                continue
            self._materialize_lair(lair_id, info)
            location_id = str(info["location_id"])
            creature_ids = self._materialized_lairs[lair_id][0]
            spawned = [
                e for cid in creature_ids if cid in self._entities and isinstance((e := self._entities[cid]), Creature)
            ]
            if spawned and location_id not in self._combat.get_combat_locations():
                self._maybe_start_combat(location_id, spawned, query_fn)

        # Dematerialize lairs no longer at active locations
        for lair_id in list(self._materialized_lairs):
            if lair_id in lairs_at_active:
                continue
            creature_ids, _core_id, _minions = self._materialized_lairs[lair_id]
            any_in_combat = any(
                isinstance(ent := self._entities.get(cid), Creature) and ent.in_combat for cid in creature_ids
            )
            if any_in_combat:
                continue
            self._dematerialize_lair(lair_id, now, emit_fn)

    def _materialize_lair(self, lair_id: str, info: dict[str, Any]) -> None:
        """Spawn a lair's current roster (core if alive + alive minions) as concrete creatures."""
        from dnd_simulator.rules.rule_brain import RuleBrain

        core_tid = info.get("core")
        minion_templates = [str(t) for t in info["members"]]
        roster: list[str] = ([str(core_tid)] if core_tid else []) + minion_templates
        faction_id = str(info["faction_id"])
        location = str(info["location_id"])

        creature_ids: list[str] = []
        core_creature_id: str | None = None
        for tid in roster:
            template = self._monster_templates[tid]
            self._spawn_counter += 1
            instance_id = f"{tid}_{self._spawn_counter}"
            creature = template.spawn(location, instance_id)
            creature.faction_id = faction_id
            creature.brain = RuleBrain()
            creature.active = True
            self._entities[creature.id] = creature
            creature_ids.append(instance_id)
            if core_tid and core_creature_id is None and tid == str(core_tid):
                core_creature_id = instance_id
            logger.info("lair_materialize", lair_id=lair_id, creature_id=instance_id)

        self._materialized_lairs[lair_id] = (creature_ids, core_creature_id, minion_templates)

    def _dematerialize_lair(self, lair_id: str, now: int, emit_fn: EmitFn | None) -> None:
        """Remove a lair's creatures and emit its surviving population so ecology can sync."""
        creature_ids, core_creature_id, minion_templates = self._materialized_lairs[lair_id]

        core_alive = bool(core_creature_id) and self._is_alive(core_creature_id)
        minion_ids = [cid for cid in creature_ids if cid != core_creature_id]
        alive_members = [tid for cid, tid in zip(minion_ids, minion_templates, strict=True) if self._is_alive(cid)]

        for cid in creature_ids:
            self._entities.pop(cid, None)
        del self._materialized_lairs[lair_id]
        logger.info("lair_dematerialize", lair_id=lair_id, alive_minions=len(alive_members), core_alive=core_alive)

        if emit_fn is not None:
            emit_fn(
                Event(
                    event_type=EventType.LAIR_DEMATERIALIZED,
                    source_layer="entities",
                    data={
                        "lair_id": lair_id,
                        "core_alive": core_alive,
                        "alive_members": alive_members,
                        "at_seconds": now,
                    },
                    description=f"Lair {lair_id} dematerialized ({len(alive_members)} minions left)",
                )
            )

    def _is_alive(self, creature_id: str | None) -> bool:
        """True if the tracked creature is still present and alive (dead temporaries are auto-removed)."""
        if creature_id is None:
            return False
        ent = self._entities.get(creature_id)
        return isinstance(ent, Creature) and ent.is_alive
