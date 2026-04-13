"""Action Surge handler — Fighter L2 bonus action grants one extra Action."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.rules.resources import has_resource, use_resource

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = structlog.get_logger(domain="action")


def handle_action_surge(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Action Surge: bonus action, consumes `action_surge` pool, grants +1 Action this turn."""
    from dnd_simulator.core.character import Character

    if not isinstance(actor, Character):
        return ActionResult(success=False, error="Only characters can use Action Surge")

    has_pool = any(p.id == "action_surge" for p in actor.resource_pools)
    if not has_pool:
        return ActionResult(success=False, error="Action Surge not available (requires Fighter L2+)")
    if not has_resource(actor, "action_surge"):
        return ActionResult(success=False, error="Action Surge already used")

    if ctx.turn_budget is None:
        return ActionResult(success=False, error="Action Surge requires an active turn")

    use_resource(actor, "action_surge")
    ctx.turn_budget.actions += 1

    logger.info("action_surge", entity_id=actor.id)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_ACTION_SURGE,
            source_layer="entities",
            data={"entity_id": actor.id},
        )
    )
    return ActionResult()
