"""Reaction action handlers — opportunity attack."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.models import ActionResult, Event, EventType

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = structlog.get_logger(domain="action")


def handle_opportunity_attack(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Opportunity attack: one melee attack as a reaction.

    Reuses the normal attack resolution by emitting ENTITY_ATTACK (combat_manager
    resolves it). Then emits an OPPORTUNITY_ATTACK log event. Consumes reaction
    directly since OA is dispatched outside the normal turn loop.
    """
    target_id = str(action.params["target_id"])

    logger.info("opportunity_attack", attacker=actor.id, target=target_id)

    # Resolve via normal attack pipeline
    result = emit_fn(
        Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={
                "attacker_id": actor.id,
                "target_id": target_id,
            },
        )
    )

    # Log OA event for combat history
    emit_fn(
        Event(
            event_type=EventType.OPPORTUNITY_ATTACK,
            source_layer="entities",
            data={
                "attacker_id": actor.id,
                "target_id": target_id,
            },
        )
    )

    return result
