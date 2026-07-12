"""Completion effects for timed creature intentions."""

from __future__ import annotations

import structlog

from dnd_simulator.core.character import Creature
from dnd_simulator.core.intent import IntentInterruptReason, TimedIntent, TravelIntent
from dnd_simulator.core.location import LocationGraph
from dnd_simulator.core.resource import RestType
from dnd_simulator.rules.resources import reset_resources

logger = structlog.get_logger(domain="intent")


def interrupt_intent(creature: Creature, reason: IntentInterruptReason) -> bool:
    """Clear an active intent once without applying its completion effects."""
    intent = creature.current_intent
    if intent is None:
        return False
    creature.current_intent = None
    logger.info(
        "intent_interrupted",
        entity_id=creature.id,
        intent_kind=intent.kind,
        reason=reason,
        location_id=creature.location_id,
    )
    return True


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


def advance_travel_leg(
    creature: Creature,
    intent: TravelIntent,
    location_graph: LocationGraph,
) -> TravelIntent | None:
    """Commit one reached route leg and return the remaining journey."""
    arrived_at = intent.remaining_route[0]
    creature.location_id = arrived_at
    remaining = intent.remaining_route[1:]
    logger.info("travel_leg_arrive", entity_id=creature.id, location_id=arrived_at)
    if not remaining:
        return None
    return TravelIntent(
        started_at_seconds=intent.started_at_seconds,
        destination_id=intent.destination_id,
        remaining_route=remaining,
        next_arrival_seconds=intent.next_arrival_seconds + location_graph.travel_seconds(arrived_at, remaining[0]),
    )
