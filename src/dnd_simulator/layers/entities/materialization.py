"""Squad and lair materialization for the entities layer — split out of ActivationManager.

Squad and lair share one algorithm: materialize a roster at an active location, track the
spawned ids, dematerialize (reconciling survivors back up) when the player leaves. The two
keep distinct roster metadata (squad: strength/spawn_count; lair: core id/minion templates),
so the trackers stay as separate dicts — also read by QueryHandler — rather than one union type.
Functions take the ActivationManager as their state owner (`mgr`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.character import Creature
from dnd_simulator.core.events import (
    LairDematerializedPayload,
    SquadDematerializedPayload,
    SquadMaterializedPayload,
)
from dnd_simulator.core.lair import LairState
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.core.queries import LairInfo, SquadInfo, query_lairs_at_location, query_squads_at_location
from dnd_simulator.layers.entities.encounters import maybe_start_combat

if TYPE_CHECKING:
    from dnd_simulator.core.models import EmitFn, QueryFn
    from dnd_simulator.layers.entities.activation_manager import ActivationManager

logger = structlog.get_logger(domain="entity")


def _any_in_combat(mgr: ActivationManager, creature_ids: list[str]) -> bool:
    """True if any tracked creature is currently in combat (block dematerialize)."""
    return any(isinstance(ent := mgr._entities.get(cid), Creature) and ent.in_combat for cid in creature_ids)


def is_alive(mgr: ActivationManager, creature_id: str | None) -> bool:
    """True if the tracked creature is still present and alive (dead temporaries are auto-removed)."""
    if creature_id is None:
        return False
    ent = mgr._entities.get(creature_id)
    return isinstance(ent, Creature) and ent.is_alive


# -- Squad materialization --


def update_squad_materialization(
    mgr: ActivationManager,
    active_locations: set[str],
    query_fn: QueryFn,
    emit_fn: EmitFn | None,
) -> None:
    """Materialize squads at active locations, dematerialize squads that left."""
    from dnd_simulator.core.world import LayerError
    from dnd_simulator.rules.rule_brain import RuleBrain

    squads_at_active: dict[str, SquadInfo] = {}
    for loc in active_locations:
        try:
            squads = query_squads_at_location(query_fn, loc)
        except LayerError:
            return  # No ecology layer in this world — skip materialization
        for squad_info in squads:
            squads_at_active[squad_info.id] = squad_info

    # Materialize new squads
    for squad_id, info in squads_at_active.items():
        if squad_id in mgr._materialized_squads:
            continue  # already materialized
        materialize_squad(mgr, squad_id, info, RuleBrain)
        # Auto-start combat if materialized creatures are hostile to someone here
        location_id = info.current_location_id
        creature_ids = mgr._materialized_squads[squad_id][0]
        spawned = [
            e for cid in creature_ids if cid in mgr._entities and isinstance((e := mgr._entities[cid]), Creature)
        ]
        if spawned and location_id not in mgr._combat.get_combat_locations():
            maybe_start_combat(mgr, location_id, spawned, query_fn)

    # Dematerialize squads no longer at active locations
    for squad_id in list(mgr._materialized_squads):
        if squad_id in squads_at_active:
            continue  # still at active location

        creature_ids, original_strength, spawn_count = mgr._materialized_squads[squad_id]
        if _any_in_combat(mgr, creature_ids):
            continue
        dematerialize_squad(mgr, squad_id, creature_ids, original_strength, spawn_count, emit_fn)


def materialize_squad(mgr: ActivationManager, squad_id: str, info: SquadInfo, brain_cls: type) -> None:
    """Spawn creatures from a squad's member templates."""
    templates: list[str] = list(info.member_templates)
    strength = info.strength
    max_strength = info.max_strength
    faction_id = info.faction_id
    location = info.current_location_id

    # Scale creature count by strength ratio
    count = max(1, round(len(templates) * strength / max_strength)) if max_strength > 0 else len(templates)
    templates_to_spawn = templates[:count]

    creature_ids: list[str] = []
    for tid in templates_to_spawn:
        template = mgr._monster_templates[tid]
        mgr._spawn_counter += 1
        instance_id = f"{tid}_{mgr._spawn_counter}"
        creature = template.spawn(location, instance_id)
        creature.squad_id = squad_id
        creature.faction_id = faction_id
        creature.brain = brain_cls()
        creature.active = True
        mgr._entities[creature.id] = creature
        creature_ids.append(instance_id)
        logger.info("squad_materialize", squad_id=squad_id, creature_id=instance_id)

    mgr._materialized_squads[squad_id] = (creature_ids, strength, len(templates_to_spawn))

    # Log materialization event so players at this location see it
    squad_name = info.name
    mat_event = Event(
        event_type=EventType.SQUAD_MATERIALIZED,
        source_layer="entities",
        data=SquadMaterializedPayload(squad_id, squad_name, location, len(creature_ids)),
        description=f"{squad_name} materialized at {location}",
    )
    mgr._location_log[location].append(mat_event)


def dematerialize_squad(
    mgr: ActivationManager,
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
        entity = mgr._entities.get(cid)
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
        mgr._entities.pop(cid, None)

    del mgr._materialized_squads[squad_id]
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
                data=SquadDematerializedPayload(squad_id, squad_name, location_id or "", new_strength),
                description=f"Squad {squad_id} dematerialized (strength {new_strength})",
            )
        )


# -- Lair materialization --


def update_lair_materialization(
    mgr: ActivationManager,
    now: int,
    active_locations: set[str],
    query_fn: QueryFn,
    emit_fn: EmitFn | None,
) -> None:
    """Materialize active lairs at active locations; dematerialize lairs the player left."""
    from dnd_simulator.core.world import LayerError

    lairs_at_active: dict[str, LairInfo] = {}
    for loc in active_locations:
        try:
            lairs = query_lairs_at_location(query_fn, loc)
        except LayerError:
            return  # No ecology layer in this world — skip lair materialization
        for lair_info in lairs:
            lairs_at_active[lair_info.id] = lair_info

    # Materialize new lairs (skip depleted — terminal, nothing spawns)
    for lair_id, info in lairs_at_active.items():
        # The treasury syncs for any lair state — a depleted (core-dead) lair still
        # has a lootable, persistent treasury at its location.
        sync_lair_treasury(mgr, lair_id, info)
        if lair_id in mgr._materialized_lairs:
            continue
        if info.state is not LairState.ACTIVE:
            continue
        materialize_lair(mgr, lair_id, info)
        location_id = info.location_id
        creature_ids = mgr._materialized_lairs[lair_id][0]
        spawned = [
            e for cid in creature_ids if cid in mgr._entities and isinstance((e := mgr._entities[cid]), Creature)
        ]
        if spawned and location_id not in mgr._combat.get_combat_locations():
            maybe_start_combat(mgr, location_id, spawned, query_fn)

    # Dematerialize lairs no longer at active locations
    for lair_id in list(mgr._materialized_lairs):
        if lair_id in lairs_at_active:
            continue
        creature_ids, _core_id, _minions = mgr._materialized_lairs[lair_id]
        if _any_in_combat(mgr, creature_ids):
            continue
        dematerialize_lair(mgr, lair_id, now, emit_fn)


def materialize_lair(mgr: ActivationManager, lair_id: str, info: LairInfo) -> None:
    """Spawn a lair's current roster (core if alive + alive minions) as concrete creatures."""
    from dnd_simulator.rules.rule_brain import RuleBrain

    core_tid = info.core
    minion_templates = list(info.members)
    roster: list[str] = ([core_tid] if core_tid else []) + minion_templates
    faction_id = info.faction_id
    location = info.location_id

    creature_ids: list[str] = []
    core_creature_id: str | None = None
    for tid in roster:
        template = mgr._monster_templates[tid]
        mgr._spawn_counter += 1
        instance_id = f"{tid}_{mgr._spawn_counter}"
        creature = template.spawn(location, instance_id)
        creature.faction_id = faction_id
        creature.brain = RuleBrain()
        creature.active = True
        mgr._entities[creature.id] = creature
        creature_ids.append(instance_id)
        if core_tid and core_creature_id is None and tid == core_tid:
            core_creature_id = instance_id
        logger.info("lair_materialize", lair_id=lair_id, creature_id=instance_id)

    mgr._materialized_lairs[lair_id] = (creature_ids, core_creature_id, minion_templates)


def treasury_core_alive(mgr: ActivationManager, lair_id: str, info: LairInfo) -> bool:
    """Current core status for the treasury gate.

    Prefer the live materialized core creature (so killing the core unlocks the
    treasury this visit, before the lair dematerializes). Fall back to the
    persisted lair flag when the lair isn't materialized (e.g. return after
    save/load). A coreless lair has nothing to gate behind → False (always open).
    """
    if lair_id in mgr._materialized_lairs:
        return is_alive(mgr, mgr._materialized_lairs[lair_id][1])
    if not info.has_core:
        return False
    return info.core_alive


def sync_lair_treasury(mgr: ActivationManager, lair_id: str, info: LairInfo) -> None:
    """Spawn the lair's persistent treasury once, then keep its open-state in sync.

    Skips lairs with no treasure block. Spawn is idempotent (deterministic id,
    survives dematerialize and save/load), so a return visit reuses whatever is
    left rather than refilling. ``is_open`` tracks the core gate every pass.
    """
    from dnd_simulator.core.container import Container
    from dnd_simulator.i18n import _

    treasure_items = info.treasure_items
    treasure_gold = info.treasure_gold
    if not treasure_items and not treasure_gold:
        return

    behind_core = info.treasure_behind_core
    is_open = (not behind_core) or (not treasury_core_alive(mgr, lair_id, info))

    container_id = f"{lair_id}_treasury"
    existing = mgr._entities.get(container_id)
    if isinstance(existing, Container):
        existing.is_open = is_open
        return

    container = Container(
        id=container_id,
        name=_("Treasure"),
        location_id=info.location_id,
        temporary=False,
        inventory=list(treasure_items),
        gold=treasure_gold,
        is_open=is_open,
    )
    mgr._entities[container_id] = container
    logger.info("lair_treasury_spawn", lair_id=lair_id, container_id=container_id, is_open=is_open)


def dematerialize_lair(mgr: ActivationManager, lair_id: str, now: int, emit_fn: EmitFn | None) -> None:
    """Remove a lair's creatures and emit its surviving population so ecology can sync."""
    creature_ids, core_creature_id, minion_templates = mgr._materialized_lairs[lair_id]

    core_alive = bool(core_creature_id) and is_alive(mgr, core_creature_id)
    minion_ids = [cid for cid in creature_ids if cid != core_creature_id]
    alive_members = [tid for cid, tid in zip(minion_ids, minion_templates, strict=True) if is_alive(mgr, cid)]

    for cid in creature_ids:
        mgr._entities.pop(cid, None)
    del mgr._materialized_lairs[lair_id]
    logger.info("lair_dematerialize", lair_id=lair_id, alive_minions=len(alive_members), core_alive=core_alive)

    if emit_fn is not None:
        emit_fn(
            Event(
                event_type=EventType.LAIR_DEMATERIALIZED,
                source_layer="entities",
                data=LairDematerializedPayload(lair_id, core_alive, tuple(alive_members), now),
                description=f"Lair {lair_id} dematerialized ({len(alive_members)} minions left)",
            )
        )
