"""Reaction action handlers — opportunity attack."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.events import AttackRequestedPayload, OpportunityAttackPayload
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

    Reuses the normal attack resolution by emitting ENTITY_ATTACK_REQUESTED (combat_manager
    resolves it). Then emits an OPPORTUNITY_ATTACK log event. Consumes reaction
    directly since OA is dispatched outside the normal turn loop.
    """
    target_id = str(action.params["target_id"])

    logger.info("opportunity_attack", attacker=actor.id, target=target_id)

    # Resolve via normal attack pipeline — flag as OA for perception
    result = emit_fn(
        Event(
            event_type=EventType.ENTITY_ATTACK_REQUESTED,
            source_layer="entities",
            data=AttackRequestedPayload(actor.id, target_id, is_opportunity_attack=True),
        )
    )

    # Log OA event for combat history
    emit_fn(
        Event(
            event_type=EventType.OPPORTUNITY_ATTACK,
            source_layer="entities",
            data=OpportunityAttackPayload(actor.id, target_id, actor.location_id),
        )
    )

    return result
