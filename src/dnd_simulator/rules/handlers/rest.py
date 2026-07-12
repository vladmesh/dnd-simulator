"""Rest action handlers — Long Rest and Short Rest."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.action import Action
from dnd_simulator.core.intent import IntentType, TimedIntent
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.resource import RestType

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
    """Long rest: sleep for eight hours, then recover on completion."""
    now = world.time.to_total_seconds()
    actor.current_intent = TimedIntent(IntentType.SLEEP, now, now + _LONG_REST_SECONDS, rest_type=RestType.LONG_REST)
    actor.active = False

    logger.info("long_rest", wake_at=actor.current_intent.wake_at_seconds)
    return ActionResult()


def handle_short_rest(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Short rest: sleep for one hour, then recover on completion."""
    now = world.time.to_total_seconds()
    actor.current_intent = TimedIntent(IntentType.SLEEP, now, now + _SHORT_REST_SECONDS, rest_type=RestType.SHORT_REST)
    actor.active = False

    logger.info("short_rest", wake_at=actor.current_intent.wake_at_seconds)
    return ActionResult()
