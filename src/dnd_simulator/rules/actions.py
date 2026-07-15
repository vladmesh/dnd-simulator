"""Action cost rules — determines what each action costs in turn budget.

Pure functions, no state.  Costs are derived from the central ActionDef
registry; class-specific overrides (Cunning Action, Metamagic, etc.) are
expressed as CostOverride data on ClassFeatures and selected at runtime
via the ``cost_mode`` action param.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_simulator.core.action_defs import CostOverride, CostType, get_action_def
from dnd_simulator.core.turn_budget import ActionCost

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature


def action_cost(action: Action, creature: Creature | None = None) -> ActionCost:
    """Determine the budget cost of an action.

    If the action carries a ``cost_mode`` param, look up a matching
    CostOverride on the creature's class features and use that cost.
    Otherwise use the default cost from ActionDef.
    """
    d = get_action_def(action.name)
    cost_mode = str(action.params["cost_mode"]) if action.params and "cost_mode" in action.params else None

    if cost_mode and creature is not None:
        for ov in collect_cost_overrides(creature):
            if ov.action_type == action.name and ov.cost_type.value == cost_mode:
                return _cost_type_to_cost(ov.cost_type, action)
        raise ValueError(f"No cost override '{cost_mode}' available for {action.name}")

    return _cost_type_to_cost(d.cost_type, action)


def _cost_type_to_cost(cost_type: CostType, action: Action) -> ActionCost:
    """Convert a CostType enum to a concrete ActionCost."""
    match cost_type:
        case CostType.FREE:
            return ActionCost()
        case CostType.ACTION:
            return ActionCost(actions=1)
        case CostType.BONUS_ACTION:
            return ActionCost(bonus_actions=1)
        case CostType.REACTION:
            return ActionCost(reaction=1)


def collect_cost_overrides(creature: Creature) -> list[CostOverride]:
    """Gather all cost overrides from a creature's class features."""
    from dnd_simulator.core.character import Character

    if not isinstance(creature, Character):
        return []
    result: list[CostOverride] = []
    for feat in creature.class_features:
        result.extend(feat.cost_overrides)
    return result


def ends_peaceful_turn(action: Action) -> bool:
    """Whether this action auto-ends a peaceful turn.

    All meaningful actions end the turn: say, attack, move, idle ("nothing to do"), etc.
    Only end_turn/skip are non-action exits handled by the caller.
    """
    return get_action_def(action.name).ends_peaceful_turn


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
