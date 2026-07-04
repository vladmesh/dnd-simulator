"""Lair population lifecycle — split out of EcologyLayer (politics pattern).

Applies dematerialize sync (survivors written back from a finished visit) and periodic
respawn. Depletion is the pure rule ``rules.lairs.should_deplete``; the roll is generated
here and injected.
"""

from __future__ import annotations

import structlog

from dnd_simulator.core.lair import Lair, LairState
from dnd_simulator.core.models import Event
from dnd_simulator.rules.dice import get_global_rng
from dnd_simulator.rules.lairs import should_deplete

logger = structlog.get_logger(domain="ecology")


def apply_lair_dematerialize(lairs: dict[str, Lair], event: Event) -> None:
    """Sync a lair's surviving population from a finished visit."""
    lair_id = str(event.data["lair_id"])
    lair = lairs.get(lair_id)
    if lair is None:
        return
    alive_members = event.data.get("alive_members")
    lair.alive_members = [str(m) for m in alive_members] if isinstance(alive_members, list) else []
    lair.core_alive = bool(event.data.get("core_alive", lair.core_alive))
    # Anchor the respawn countdown to this visit so respawn waits a full interval afterwards.
    lair.last_respawn_time = int(event.data.get("at_seconds", lair.last_respawn_time))

    # Depletion decision is a pure rule; the roll is generated here and injected.
    roll = get_global_rng().random()
    if should_deplete(lair, roll):
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
