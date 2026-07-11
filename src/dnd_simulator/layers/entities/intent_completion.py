"""Completion effects for timed creature intentions."""

from __future__ import annotations

import structlog

from dnd_simulator.core.character import Creature
from dnd_simulator.core.intent import TimedIntent
from dnd_simulator.core.resource import RestType
from dnd_simulator.rules.resources import reset_resources

logger = structlog.get_logger(domain="intent")


def complete_timed_intent(creature: Creature, intent: TimedIntent) -> None:
    """Apply completion effects for an elapsed intent exactly once."""
    if intent.rest_type is None:
        return

    reset_ids = reset_resources(creature, intent.rest_type)
    healed = creature.heal(creature.max_hp) if intent.rest_type is RestType.LONG_REST else 0
    logger.info(
        "rest_complete",
        entity_id=creature.id,
        rest_type=intent.rest_type,
        reset_pools=reset_ids,
        healed=healed,
    )
