"""Completion effects for timed creature intentions."""

from __future__ import annotations

import structlog

from dnd_simulator.core.character import Creature
from dnd_simulator.core.intent import TimedIntent, TravelIntent
from dnd_simulator.core.location import LocationGraph
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


def advance_travel_intent(
    creature: Creature,
    intent: TravelIntent,
    now_seconds: int,
    location_graph: LocationGraph,
) -> TravelIntent | None:
    """Advance every route leg whose arrival boundary has elapsed."""
    current = intent
    while now_seconds >= current.next_arrival_seconds:
        arrived_at = current.remaining_route[0]
        creature.location_id = arrived_at
        remaining = current.remaining_route[1:]
        logger.info("travel_leg_arrive", entity_id=creature.id, location_id=arrived_at)
        if not remaining:
            return None
        next_arrival = current.next_arrival_seconds + location_graph.travel_seconds(arrived_at, remaining[0])
        current = TravelIntent(
            started_at_seconds=current.started_at_seconds,
            destination_id=current.destination_id,
            remaining_route=remaining,
            next_arrival_seconds=next_arrival,
        )
    return current
