"""Proximity-based activation for the entities layer.

The activation passes (anchor players, activate/dormify creatures) live here. Encounter
rolling and squad/lair materialization are isolated in sibling modules (``encounters``,
``materialization``) — this class owns only the activation loop and delegates the rest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.models import Event
from dnd_simulator.core.monster import EncounterEntry
from dnd_simulator.layers.entities.encounters import check_encounters
from dnd_simulator.layers.entities.materialization import update_lair_materialization, update_squad_materialization

if TYPE_CHECKING:
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn
    from dnd_simulator.core.monster import MonsterTemplate
    from dnd_simulator.layers.entities.combat_manager import CombatManager

logger = structlog.get_logger(domain="entity")


class ActivationManager:
    """Proximity-based activation: anchor players activate nearby creatures, the rest go dormant.

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
        check_encounters(self, time, previously_active, query_fn)

        # Fourth pass: squad + lair materialization/dematerialization
        if query_fn is not None:
            update_squad_materialization(self, player_locations, query_fn, emit_fn)
            update_lair_materialization(self, now, player_locations, query_fn, emit_fn)
