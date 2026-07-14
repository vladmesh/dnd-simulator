"""Lair population lifecycle — split out of EcologyLayer (politics pattern).

Applies dematerialize sync (survivors written back from a finished visit) and periodic
respawn. Depletion is the pure rule ``rules.lairs.should_deplete``; the roll is generated
here and injected.
"""

from __future__ import annotations

import random

import structlog

from dnd_simulator.core.events import EntityDiedPayload, LairDematerializedPayload
from dnd_simulator.core.lair import Lair, LairMemberRole, LairState
from dnd_simulator.core.models import Event
from dnd_simulator.rules.lairs import should_deplete

logger = structlog.get_logger(domain="ecology")


def apply_lair_death(lairs: dict[str, Lair], payload: EntityDiedPayload) -> None:
    """Write a concrete lair creature death back to its abstract population once."""
    origin = payload.lair_origin
    if origin is None:
        return
    lair = lairs.get(origin.lair_id)
    if lair is None or payload.entity_id in lair.death_writebacks:
        return

    if origin.role is LairMemberRole.CORE:
        if origin.template_id != lair.core:
            return
        lair.core_alive = False
        lair.state = LairState.DEPLETED
    else:
        if origin.template_id not in lair.members:
            return
        if lair.alive_members is None:
            lair.alive_members = list(lair.members)
        try:
            lair.alive_members.remove(origin.template_id)
        except ValueError:
            return

    lair.death_writebacks.add(payload.entity_id)
    logger.info(
        "lair_death_written_back",
        lair_id=lair.id,
        entity_id=payload.entity_id,
        role=origin.role.value,
        state=lair.state.value,
    )


def apply_lair_dematerialize(lairs: dict[str, Lair], event: Event, rng: random.Random) -> None:
    """Sync a lair's surviving population from a finished visit."""
    payload = event.data
    assert isinstance(payload, LairDematerializedPayload)
    lair_id = payload.lair_id
    lair = lairs.get(lair_id)
    if lair is None:
        return
    lair.alive_members = list(payload.alive_members)
    if lair.state is not LairState.DEPLETED:
        lair.core_alive = payload.core_alive
    # Anchor the respawn countdown to this visit so respawn waits a full interval afterwards.
    lair.last_respawn_time = payload.at_seconds

    # Depletion decision is a pure rule; the roll is generated here and injected.
    roll = rng.random()
    if lair.state is not LairState.DEPLETED and should_deplete(lair, roll):
        lair.state = LairState.DEPLETED

    logger.info(
        "lair_population_updated",
        lair_id=lair_id,
        alive_members=len(lair.alive_members),
        core_alive=lair.core_alive,
        state=lair.state.value,
    )


def respawn_lairs(lairs: dict[str, Lair], now: int) -> None:
    """Refill ACTIVE lairs to their full roster once respawn_interval has elapsed since the last visit."""
    for lair in lairs.values():
        if lair.state is not LairState.ACTIVE:
            continue
        if lair.alive_members is None or len(lair.alive_members) >= len(lair.members):
            continue  # already at full roster
        if now - lair.last_respawn_time < lair.respawn_interval:
            continue
        lair.alive_members = None  # back to full roster
        lair.last_respawn_time = now
        logger.info("lair_respawn", lair_id=lair.id)
