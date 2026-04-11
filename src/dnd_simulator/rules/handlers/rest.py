"""Rest action handlers — Long Rest and Short Rest."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.action import Action
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.resource import RestType
from dnd_simulator.rules.resources import reset_resources

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = structlog.get_logger(domain="rest")

_LONG_REST_SECONDS = 8 * 3600  # 8 hours
_SHORT_REST_SECONDS = 1 * 3600  # 1 hour


def handle_long_rest(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Long rest: reset all resource pools, heal to full, advance 8 hours."""
    reset_ids = reset_resources(actor, RestType.LONG_REST)
    healed = actor.heal(actor.max_hp)

    now = world.time.to_total_seconds()
    actor.wake_at_seconds = now + _LONG_REST_SECONDS
    actor.active = False

    logger.info("long_rest", healed=healed, reset_pools=reset_ids, wake_at=actor.wake_at_seconds)
    return ActionResult()


def handle_short_rest(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Short rest: reset short-rest pools only, advance 1 hour. No healing."""
    reset_ids = reset_resources(actor, RestType.SHORT_REST)

    now = world.time.to_total_seconds()
    actor.wake_at_seconds = now + _SHORT_REST_SECONDS
    actor.active = False

    logger.info("short_rest", reset_pools=reset_ids, wake_at=actor.wake_at_seconds)
    return ActionResult()
