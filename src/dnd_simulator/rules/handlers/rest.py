"""Rest action handlers — Long Rest and Short Rest."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.action import Action
from dnd_simulator.core.intent import IntentType, TimedIntent
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.resource import RestType
from dnd_simulator.i18n import _

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
    """Long rest: sleep for eight hours, then recover on completion.

    Defense-in-depth gate: re-checks combat membership directly against the
    authoritative query, independent of the dispatch context's mode — a stale
    or legacy peaceful context must not let a real combat participant rest.
    """
    if world.creature_host.get_active_combat_for(actor.id) is not None:
        return ActionResult(success=False, error=_("Cannot rest while in combat"))

    now = world.time.to_total_seconds()
    actor.current_intent = TimedIntent(IntentType.SLEEP, now, now + _LONG_REST_SECONDS, rest_type=RestType.LONG_REST)
    world.creature_host.dormify(actor)

    logger.info("long_rest", wake_at=actor.current_intent.wake_at_seconds)
    return ActionResult()


def handle_short_rest(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Short rest: sleep for one hour, then recover on completion.

    Defense-in-depth gate: re-checks combat membership directly against the
    authoritative query, independent of the dispatch context's mode — a stale
    or legacy peaceful context must not let a real combat participant rest.
    """
    if world.creature_host.get_active_combat_for(actor.id) is not None:
        return ActionResult(success=False, error=_("Cannot rest while in combat"))

    now = world.time.to_total_seconds()
    actor.current_intent = TimedIntent(IntentType.SLEEP, now, now + _SHORT_REST_SECONDS, rest_type=RestType.SHORT_REST)
    world.creature_host.dormify(actor)

    logger.info("short_rest", wake_at=actor.current_intent.wake_at_seconds)
    return ActionResult()
