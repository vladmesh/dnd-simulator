"""Action cost rules — determines what each action costs in turn budget.

Pure functions, no state. Concrete per-class/per-level rules will be added later;
for now uses D&D 5e defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.turn_budget import ActionCost

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature

# Actions that cost 0 budget (information-only, free actions)
_FREE_ACTIONS = frozenset({ActionType.IDLE, ActionType.END_TURN, ActionType.SKIP})

# Actions that cost 1 standard action
_STANDARD_ACTIONS = frozenset(
    {ActionType.ATTACK, ActionType.DODGE, ActionType.FLEE, ActionType.DASH, ActionType.USE_ITEM}
)

# Actions that cost 1 bonus action
_BONUS_ACTIONS: frozenset[str] = frozenset()

# Actions that use movement (cost = ft param)
_MOVEMENT_ACTIONS = frozenset({ActionType.MOVE})

# Peaceful actions that auto-end the turn.
# idle = "nothing to do", so it ends the turn too (prevents NPC infinite loops).
_TURN_ENDING_PEACEFUL = frozenset(
    {
        ActionType.IDLE,
        ActionType.SAY,
        ActionType.ATTACK,
        ActionType.WAIT,
        ActionType.MOVE,
        ActionType.DASH,
        ActionType.FLEE,
        ActionType.DODGE,
        ActionType.USE_ITEM,
    }
)


def action_cost(action: Action) -> ActionCost:
    """Determine the budget cost of an action.

    Free actions (idle, say, end_turn, skip) cost nothing.
    Standard actions (attack, dodge, dash, flee) cost 1 action.
    Movement costs feet based on creature speed (simplified: 5ft per move action for now).
    """
    name = action.name

    if name in _FREE_ACTIONS or name == ActionType.SAY:
        return ActionCost()

    if name in _STANDARD_ACTIONS:
        return ActionCost(actions=1)

    if name in _BONUS_ACTIONS:
        return ActionCost(bonus_actions=1)

    if name in _MOVEMENT_ACTIONS:
        ft = int(str(action.params.get("ft", 5))) if action.params else 5
        return ActionCost(movement_ft=ft)

    # Unknown actions are free (safe default — don't block gameplay)
    return ActionCost()


def ends_peaceful_turn(action: Action) -> bool:
    """Whether this action auto-ends a peaceful turn.

    All meaningful actions end the turn: say, attack, move, idle ("nothing to do"), etc.
    Only end_turn/skip are non-action exits handled by the caller.
    """
    return action.name in _TURN_ENDING_PEACEFUL


def get_num_actions(creature: Creature) -> int:
    """How many standard actions this creature gets per turn.

    Default: 1. Fighter Extra Attack, Action Surge, etc. will add more.
    """
    _ = creature  # will use class/level later
    return 1


def get_num_bonus_actions(creature: Creature) -> int:
    """How many bonus actions this creature gets per turn.

    Default: 1. Some features may grant additional bonus actions.
    """
    _ = creature  # will use class/features later
    return 1
