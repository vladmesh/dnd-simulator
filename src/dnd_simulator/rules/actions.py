"""Action cost rules — determines what each action costs in turn budget.

Pure functions, no state. Concrete per-class/per-level rules will be added later;
for now uses D&D 5e defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_simulator.core.turn_budget import ActionCost

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature

# Actions that cost 0 budget (information-only, free actions)
_FREE_ACTIONS = frozenset({"idle", "end_turn", "skip"})

# Actions that cost 1 standard action (dash handled specially by Round)
_STANDARD_ACTIONS = frozenset({"attack", "dodge", "flee"})

# Actions that cost 1 bonus action
_BONUS_ACTIONS: frozenset[str] = frozenset()

# Actions that use movement (cost = ft param)
_MOVEMENT_ACTIONS = frozenset({"move"})

# Dash is a special action handled by Round: costs 1 action, adds speed to movement pool
DASH_ACTION_COST = ActionCost(actions=1)

# Peaceful actions that auto-end the turn (meaningful world interactions).
# Queries (idle = look/status/map) do NOT end the turn — they just refresh awareness.
_TURN_ENDING_PEACEFUL = frozenset({"say", "attack", "wait", "move", "dash", "flee", "dodge"})


def action_cost(action: Action) -> ActionCost:
    """Determine the budget cost of an action.

    Free actions (idle, say, end_turn, skip, look, status, map) cost nothing.
    Standard actions (attack, dodge, dash, flee) cost 1 action.
    Movement costs feet based on creature speed (simplified: 5ft per move action for now).
    """
    name = action.name

    if name in _FREE_ACTIONS or name == "say":
        return ActionCost()

    if name in _STANDARD_ACTIONS:
        return ActionCost(actions=1)

    if name in _BONUS_ACTIONS:
        return ActionCost(bonus_actions=1)

    if name in _MOVEMENT_ACTIONS:
        ft = int(action.params.get("ft", 5)) if action.params else 5
        return ActionCost(movement_ft=ft)

    # Unknown actions are free (safe default — don't block gameplay)
    return ActionCost()


def ends_peaceful_turn(action: Action) -> bool:
    """Whether this action auto-ends a peaceful turn.

    Turn-ending actions are meaningful world interactions (say, attack, move, etc.).
    Non-ending actions are UI queries (idle = look/status/map) that just refresh awareness.
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
