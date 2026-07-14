"""Encounter rolling for the entities layer — split out of ActivationManager.

Functions take the ActivationManager as their state owner (`mgr`) and read/mutate the
shared entity / log / cooldown references it holds. The activation passes themselves stay
on ActivationManager; this module owns only the "did someone arrive → roll monsters" path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.character import Creature
from dnd_simulator.core.events import EncounterSpawnedPayload
from dnd_simulator.core.lair import LairState
from dnd_simulator.core.models import Event, EventType, FactionRelation
from dnd_simulator.core.queries import query_faction_relation, query_is_daylight, query_lairs_at_location
from dnd_simulator.rules.encounters import is_active_at_time

if TYPE_CHECKING:
    from dnd_simulator.core.models import GameDateTime, QueryFn
    from dnd_simulator.layers.entities.activation_manager import ActivationManager

logger = structlog.get_logger(domain="entity")

ENCOUNTER_COOLDOWN_SECONDS = 600  # 10 minutes


def check_encounters(
    mgr: ActivationManager, time: GameDateTime, active_ids: set[str], query_fn: QueryFn | None = None
) -> None:
    """Roll encounters for locations where any active creature just arrived."""
    now = time.to_total_seconds()
    for e in list(mgr._entities.values()):
        if not isinstance(e, Creature):
            continue
        if e.id not in active_ids or e.temporary:
            continue

        prev = mgr._creature_locations.get(e.id)
        mgr._creature_locations[e.id] = e.location_id

        if e.location_id == prev:
            continue  # didn't move

        logger.info(
            "encounter_check_moved",
            entity_id=e.id,
            from_location=prev or "(new)",
            to_location=e.location_id,
            has_table=e.location_id in mgr._encounter_tables,
        )

        if e.location_id not in mgr._encounter_tables:
            continue  # no encounters here

        # Skip random encounters at locations with an active lair — the lair IS the encounter
        if has_active_lair(mgr, e.location_id, query_fn):
            logger.info("encounter_check_lair_skip", location=e.location_id, entity_id=e.id)
            continue

        # Check cooldown
        last_roll = mgr._encounter_cooldowns.get(e.location_id, 0)
        if now - last_roll < ENCOUNTER_COOLDOWN_SECONDS:
            logger.info("encounter_check_cooldown", location=e.location_id, entity_id=e.id)
            continue

        mgr._encounter_cooldowns[e.location_id] = now
        roll_encounters(mgr, e.location_id, time, query_fn)


def has_active_lair(mgr: ActivationManager, location_id: str, query_fn: QueryFn | None) -> bool:
    """Return True if an active lair occupies this location."""
    if query_fn is None:
        return False
    from dnd_simulator.core.world import LayerError

    try:
        lairs = query_lairs_at_location(query_fn, location_id)
        return any(info.state is LairState.ACTIVE for info in lairs)
    except LayerError:
        return False


def roll_encounters(
    mgr: ActivationManager, location_id: str, time: GameDateTime, query_fn: QueryFn | None = None
) -> None:
    """Roll each encounter entry for a location and spawn monsters.

    Entries tagged with a time of day roll only in the matching phase; the
    day/night signal comes from the geography layer.
    """
    from dnd_simulator.rules.rule_brain import RuleBrain

    entries = mgr._encounter_tables[location_id]
    is_day = is_daylight_at(mgr, location_id, time, query_fn)
    spawned_names: list[str] = []
    spawned_creatures: list[Creature] = []

    logger.info("encounter_rolling", location=location_id, entries=len(entries), is_day=is_day)
    for entry in entries:
        if not is_active_at_time(entry.time_of_day, is_day):
            logger.info(
                "encounter_roll_off_hours",
                location=location_id,
                template=entry.template_id,
                time_of_day=entry.time_of_day,
                is_day=is_day,
            )
            continue
        roll = mgr._rng.random()
        if roll >= entry.chance:
            logger.info(
                "encounter_roll_miss",
                location=location_id,
                template=entry.template_id,
                roll=round(roll, 3),
                chance=entry.chance,
            )
            continue
        template = mgr._monster_templates[entry.template_id]
        count = mgr._rng.randint(entry.count_min, entry.count_max)
        for _ in range(count):
            mgr._spawn_counter += 1
            instance_id = f"{template.id}_{mgr._spawn_counter}"
            creature = template.spawn(location_id, instance_id)
            creature.brain = RuleBrain()
            mgr._entities[creature.id] = creature
            creature.active = True
            spawned_names.append(creature.name)
            spawned_creatures.append(creature)
            logger.info("encounter_spawn", entity_id=instance_id, location=location_id)

    if spawned_names:
        event = Event(
            event_type=EventType.ENCOUNTER_SPAWNED,
            source_layer="entities",
            data=EncounterSpawnedPayload(
                location_id=location_id,
                spawned_names=tuple(spawned_names),
                spawned_entity_ids=tuple(creature.id for creature in spawned_creatures),
            ),
        )
        mgr._location_log[location_id].append(event)

        # Auto-start combat if spawned creatures are hostile to anyone at this location
        if query_fn is not None and location_id not in mgr._combat.get_combat_locations():
            maybe_start_combat(mgr, location_id, spawned_creatures, query_fn)


def is_daylight_at(mgr: ActivationManager, location_id: str, time: GameDateTime, query_fn: QueryFn | None) -> bool:
    """Ask geography whether it is day at a location. Defaults to day when unknown.

    Defaulting to day means an absent/queryless geography never suppresses an
    untagged spawn (untagged is always active) — only explicit night/day tags
    ever depend on this signal.
    """
    if query_fn is None:
        return True
    from dnd_simulator.core.world import LayerError

    try:
        return query_is_daylight(query_fn, location_id=location_id, month=time.month, hour=time.hour)
    except LayerError:
        return True  # no geography layer in this world


def maybe_start_combat(mgr: ActivationManager, location_id: str, spawned: list[Creature], query_fn: QueryFn) -> None:
    """Start combat if any spawned creature is hostile to an existing creature at the location."""
    existing = [
        e
        for e in mgr._entities.values()
        if isinstance(e, Creature) and e.location_id == location_id and e.is_alive and e not in spawned
    ]
    for sc in spawned:
        if not sc.faction_id:
            continue
        for ex in existing:
            if not ex.faction_id:
                continue
            try:
                if query_faction_relation(query_fn, sc.faction_id, ex.faction_id) is FactionRelation.HOSTILE:
                    logger.info(
                        "encounter_auto_combat",
                        location=location_id,
                        spawned_faction=sc.faction_id,
                        existing_faction=ex.faction_id,
                    )
                    mgr._combat.start_combat(location_id)
                    return
            except Exception:
                pass
