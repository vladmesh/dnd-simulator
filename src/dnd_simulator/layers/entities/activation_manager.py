"""Proximity-based activation for the entities layer.

The activation passes (anchor creatures, activate/dormify creatures) live here. Encounter
rolling and squad/lair materialization are isolated in sibling modules (``encounters``,
``materialization``) — this class owns only the activation loop and delegates the rest.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.inner_self import DigestBoundary
from dnd_simulator.core.intent import IntentInterruptReason, TimedIntent, TravelIntent
from dnd_simulator.core.models import Event
from dnd_simulator.core.monster import EncounterEntry
from dnd_simulator.core.triggers import GmActivationOverride
from dnd_simulator.layers.entities.encounters import check_encounters
from dnd_simulator.layers.entities.intent_completion import (
    advance_travel_leg,
    complete_timed_intent,
    interrupt_intent,
)
from dnd_simulator.layers.entities.materialization import (
    dematerialize_unobserved_encounters,
    update_lair_materialization,
    update_squad_materialization,
    withdraw_survivor,
)
from dnd_simulator.layers.entities.save_models import MaterializationSave, MaterializedLairSave, MaterializedSquadSave

if TYPE_CHECKING:
    from dnd_simulator.core.location import LocationGraph
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn
    from dnd_simulator.core.monster import MonsterTemplate
    from dnd_simulator.layers.entities.combat_manager import CombatManager

logger = structlog.get_logger(domain="entity")


class ActivationManager:
    """Proximity-based activation: anchors activate nearby creatures, the rest go dormant.

    Operates on shared entity and state references owned by EntitiesLayer. Encounter rolling and
    materialization are delegated to the ``encounters`` / ``materialization`` sibling modules.
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
        rng: random.Random,
        digest: Callable[[Creature, DigestBoundary], None],
        dormify: Callable[[Creature], None],
        record_event: Callable[[Event], None],
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
        self._rng = rng
        self._digest = digest
        self._dormify = dormify
        self._record_event = record_event
        self._spawn_counter = 0
        # Squad/lair members that fled alive: removed from the world, still counted by their roster.
        self._withdrawn_survivors: set[str] = set()

    def materialization_state(self) -> MaterializationSave:
        """Roster trackers for the save: who each materialized squad/lair spawned and who fled alive."""
        return MaterializationSave(
            spawn_counter=self._spawn_counter,
            squads={
                squad_id: MaterializedSquadSave(creature_ids=list(ids), original_strength=strength, spawn_count=count)
                for squad_id, (ids, strength, count) in self._materialized_squads.items()
            },
            lairs={
                lair_id: MaterializedLairSave(
                    creature_ids=list(ids), core_creature_id=core_id, minion_templates=list(minions)
                )
                for lair_id, (ids, core_id, minions) in self._materialized_lairs.items()
            },
            withdrawn_survivors=sorted(self._withdrawn_survivors),
        )

    def load_materialization_state(self, save: MaterializationSave) -> None:
        """Restore the roster trackers in place (the dicts are shared with the layer and QueryHandler)."""
        self._spawn_counter = save.spawn_counter
        self._materialized_squads.clear()
        self._materialized_squads.update(
            {
                squad_id: (list(squad.creature_ids), squad.original_strength, squad.spawn_count)
                for squad_id, squad in save.squads.items()
            }
        )
        self._materialized_lairs.clear()
        self._materialized_lairs.update(
            {
                lair_id: (list(lair.creature_ids), lair.core_creature_id, list(lair.minion_templates))
                for lair_id, lair in save.lairs.items()
            }
        )
        self._withdrawn_survivors = set(save.withdrawn_survivors)

    def withdraw_anonymous(self, creature: Creature) -> None:
        """Take an anonymous creature off the world; a squad/lair member stays in its roster alive."""
        withdraw_survivor(self, creature)

    def release_scene(self, location_id: str) -> None:
        """A fight ended at a location no anchor holds: its random encounter goes back.

        Squads and lairs dematerialize on the next activation pass with their strength
        accounting; named creatures stay as they are.
        """
        if any(
            isinstance(e, Creature) and e.is_alive and e.is_anchor and e.current_intent is None
            for e in self._entities.values()
            if e.location_id == location_id
        ):
            return
        dematerialize_unobserved_encounters(self, location_id)

    def update_activation(
        self,
        time: GameDateTime,
        query_fn: QueryFn | None = None,
        emit_fn: EmitFn | None = None,
        location_graph: LocationGraph | None = None,
    ) -> None:
        """Activate creatures near awake anchors, dormify the rest.

        Rules:
        - Any living creature explicitly marked as an anchor holds its location active.
        - An anchor with a timed intent is dormant until its timer expires.
        - Creatures at an anchor's location are active.
        - Creatures in combat are active (don't interrupt fights).
        - A creature on a pending journey (``TravelIntent``) is dormant unless in combat.
        - Proximity never cancels a timed intent.
        - Everyone else is dormant (active=False).

        When query_fn/emit_fn are provided, also handles squad materialization:
        squads at active locations are spawned as creatures, squads no longer
        at active locations are dematerialized with strength updates.

        """
        from dnd_simulator.layers.entities.models import Npc

        now = time.to_total_seconds()
        hour = time.hour

        # Snapshot active creature IDs before re-evaluation (for encounter checks).
        previously_active: set[str] = {e.id for e in self._entities.values() if isinstance(e, Creature) and e.active}

        # Capture scenes held before arrivals. Travelers reaching one of these
        # locations stop there instead of crossing it in one update.
        occupied_scene_locations: set[str] = set()
        for e in self._entities.values():
            if not isinstance(e, Creature):
                continue
            if not e.is_alive:
                self._dormify(e)
                e.current_intent = None
                continue
            if e.is_anchor and e.current_intent is None:
                effective_location = e.current_location(hour) if isinstance(e, Npc) else e.location_id
                occupied_scene_locations.add(effective_location)

        # First pass: expire timers and advance elapsed travel boundaries.
        for e in self._entities.values():
            if not isinstance(e, Creature) or not e.is_alive:
                continue
            if isinstance(e.current_intent, TimedIntent) and now >= e.current_intent.wake_at_seconds:
                complete_timed_intent(e, e.current_intent, self._digest)
                e.current_intent = None
                logger.info("activation_wake_timer", entity_id=e.id)
            while isinstance(e.current_intent, TravelIntent) and now >= e.current_intent.next_arrival_seconds:
                if location_graph is None:
                    raise RuntimeError("location graph is required to advance travel")
                e.current_intent = advance_travel_leg(e, e.current_intent, location_graph, self._digest)
                if e.current_intent is not None and e.location_id in occupied_scene_locations:
                    interrupt_intent(e, IntentInterruptReason.SCENE, self._digest)
                    break

        # Collect locations held after completions and interruptions.
        anchor_locations: set[str] = set()
        for e in self._entities.values():
            if not isinstance(e, Creature) or not e.is_alive:
                continue
            if e.is_anchor and e.current_intent is None:
                effective_location = e.current_location(hour) if isinstance(e, Npc) else e.location_id
                anchor_locations.add(effective_location)

        # Second pass: recompute every creature from independent activation reasons.
        for e in self._entities.values():
            if not isinstance(e, Creature):
                continue
            if not e.is_alive:
                self._dormify(e)
                continue

            effective_location = e.location_id
            if isinstance(e, Npc):
                effective_location = e.current_location(hour)

            scene_active = e.current_intent is None and effective_location in anchor_locations
            trigger_active = any(trigger.armed and trigger.active for trigger in e.triggers)
            automatic_active = trigger_active and e.gm_activation_override is not GmActivationOverride.DORMANT
            manual_active = e.gm_activation_override is GmActivationOverride.ACTIVE
            # Authoritative combat membership, not the transitional Creature.in_combat flag —
            # a stale flag must not dormify an actual active-CombatState participant.
            in_combat = self._combat.get_active_combat_for(e.id) is not None
            # A creature on the road (e.g. a fleer) is on no scene until its arrival boundary:
            # no standing activation reason may wake it where it set out from.
            on_the_road = isinstance(e.current_intent, TravelIntent)
            should_activate = in_combat or (
                not on_the_road and (scene_active or e.always_active or automatic_active or manual_active)
            )
            if should_activate:
                e.active = True
            else:
                self._dormify(e)

            # Move NPC to their scheduled location when activated
            if should_activate and effective_location != e.location_id:
                e.location_id = effective_location

        # Third pass: check for encounter spawns from creatures that were active
        check_encounters(self, time, previously_active, query_fn)

        # Fourth pass: squad + lair materialization/dematerialization
        if query_fn is not None:
            update_squad_materialization(self, anchor_locations, query_fn, emit_fn)
            update_lair_materialization(self, now, anchor_locations, query_fn, emit_fn)
