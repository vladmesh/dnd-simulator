"""Action validation — pure precondition checks before action execution.

No state, no I/O. Takes actor + action + context, returns error or None.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.i18n import _

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.turn_budget import TurnBudget


@dataclass(frozen=True)
class ActionContext:
    """Minimal context needed for action validation."""

    is_combat: bool
    current_turn_entity_id: str | None = None  # whose turn (None = outside round)
    turn_budget: TurnBudget | None = None


@dataclass(frozen=True)
class ValidationError:
    """Validation failure with machine-readable code and human message."""

    code: str
    message: str


# Actions that only make sense in combat
_COMBAT_ONLY: frozenset[ActionType] = frozenset({ActionType.DODGE, ActionType.FLEE, ActionType.DASH})

# Actions blocked during combat (speech goes through action description field)
_COMBAT_BLOCKED: frozenset[ActionType] = frozenset({ActionType.SAY})


def validate_action(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """Run all precondition checks. Returns first error or None if valid."""
    for check in _CHECKS:
        error = check(actor, action, ctx)
        if error is not None:
            return error
    return None


def check_actor_alive(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """Dead creatures cannot act."""
    if not actor.is_alive:
        return ValidationError("DEAD_ACTOR", _("Dead creatures cannot act"))
    return None


def check_actor_active(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """Dormant creatures cannot act."""
    if not actor.active:
        return ValidationError("DORMANT_ACTOR", _("Dormant creatures cannot act"))
    return None


def check_action_mode(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """Combat-only actions outside combat and vice versa."""
    if ctx.is_combat and action.name in _COMBAT_BLOCKED:
        return ValidationError(
            "WRONG_MODE",
            _("'{action}' is not available in combat").format(action=action.name),
        )
    if not ctx.is_combat and action.name in _COMBAT_ONLY:
        return ValidationError(
            "WRONG_MODE",
            _("'{action}' is not available outside combat").format(action=action.name),
        )
    return None


_CHECKS = [
    check_actor_alive,
    check_actor_active,
    check_action_mode,
]
