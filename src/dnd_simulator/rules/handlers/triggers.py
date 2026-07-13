"""Activation trigger action handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.triggers import CompleteTriggerStatus, complete_trigger
from dnd_simulator.i18n import _

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext


def handle_complete_trigger(
    actor: Creature,
    action: Action,
    emit_fn: EmitFn,
    ctx: ActionContext,
    world: World,
) -> ActionResult:
    """Mark exactly one armed active trigger as complete."""
    trigger_id = str(action.params["trigger_id"])
    status = complete_trigger(actor.triggers, trigger_id)
    if status is CompleteTriggerStatus.UNKNOWN:
        return ActionResult(success=False, error=_("Unknown activation trigger '{id}'").format(id=trigger_id))
    if status is CompleteTriggerStatus.DISARMED:
        return ActionResult(success=False, error=_("Activation trigger '{id}' is disarmed").format(id=trigger_id))
    if status is CompleteTriggerStatus.INACTIVE:
        return ActionResult(success=False, error=_("Activation trigger '{id}' is not active").format(id=trigger_id))
    return ActionResult()
