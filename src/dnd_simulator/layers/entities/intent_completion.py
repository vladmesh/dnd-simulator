"""Completion effects for timed creature intentions."""

from __future__ import annotations

from collections.abc import Callable

import structlog

from dnd_simulator.core.character import Creature
from dnd_simulator.core.inner_self import DigestBoundary
from dnd_simulator.core.intent import IntentInterruptReason, TimedIntent, TravelIntent
from dnd_simulator.core.location import LocationGraph
from dnd_simulator.core.resource import RestType
from dnd_simulator.rules.resources import reset_resources

logger = structlog.get_logger(domain="intent")
DigestFn = Callable[[Creature, DigestBoundary], None]


def interrupt_intent(creature: Creature, reason: IntentInterruptReason, digest: DigestFn | None = None) -> bool:
    """Clear an active intent once without applying its completion effects."""
    intent = creature.current_intent
    if intent is None:
        return False
    creature.current_intent = None
    if digest is not None:
        digest(creature, DigestBoundary.INTENT_INTERRUPTED)
    logger.info(
        "intent_interrupted",
        entity_id=creature.id,
        intent_kind=intent.kind,
        reason=reason,
        location_id=creature.location_id,
    )
    return True


def complete_timed_intent(creature: Creature, intent: TimedIntent, digest: DigestFn | None = None) -> None:
    """Apply completion effects for an elapsed intent exactly once."""
    if intent.rest_type is None:
        if digest is not None:
            digest(creature, DigestBoundary.INTENT_COMPLETED)
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
    if digest is not None:
        digest(creature, DigestBoundary.INTENT_COMPLETED)


def advance_travel_leg(
    creature: Creature,
    intent: TravelIntent,
    location_graph: LocationGraph,
    digest: DigestFn | None = None,
) -> TravelIntent | None:
    """Commit one reached route leg and return the remaining journey."""
    arrived_at = intent.remaining_route[0]
    creature.location_id = arrived_at
    remaining = intent.remaining_route[1:]
    logger.info("travel_leg_arrive", entity_id=creature.id, location_id=arrived_at)
    if not remaining:
        if digest is not None:
            digest(creature, DigestBoundary.INTENT_COMPLETED)
        return None
    return TravelIntent(
        started_at_seconds=intent.started_at_seconds,
        destination_id=intent.destination_id,
        remaining_route=remaining,
        next_arrival_seconds=intent.next_arrival_seconds + location_graph.travel_seconds(arrived_at, remaining[0]),
    )
