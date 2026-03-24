"""Action validation — pure precondition checks before action execution.

No state, no I/O. Takes actor + action + context, returns error or None.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.i18n import _
from dnd_simulator.rules.actions import action_cost

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature, Entity
    from dnd_simulator.core.combat import CombatState
    from dnd_simulator.core.turn_budget import TurnBudget


# Type alias for entity lookup — returns Entity or None given an ID.
EntityLookup = Callable[[str], "Entity | None"]


@dataclass(frozen=True)
class ActionContext:
    """Context needed for action validation."""

    is_combat: bool
    current_turn_entity_id: str | None = None  # whose turn (None = outside round)
    turn_budget: TurnBudget | None = None
    combat_state: CombatState | None = None  # for reach checks via BattleMap
    get_entity: EntityLookup | None = field(default=None, repr=False)  # for target validation


@dataclass(frozen=True)
class ValidationError:
    """Validation failure with machine-readable code and human message."""

    code: str
    message: str


# Actions that only make sense in combat
_COMBAT_ONLY: frozenset[ActionType] = frozenset({ActionType.DODGE, ActionType.FLEE, ActionType.DASH})

# Actions blocked during combat
_COMBAT_BLOCKED: frozenset[ActionType] = frozenset({ActionType.SAY, ActionType.IDLE, ActionType.WAIT})

# Actions that take a target_id param
_TARGETED: frozenset[ActionType] = frozenset({ActionType.ATTACK})


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


def check_budget(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """Turn budget must cover the action cost."""
    if ctx.turn_budget is None:
        return None
    cost = action_cost(action)
    if not ctx.turn_budget.can_afford(cost):
        return ValidationError(
            "INSUFFICIENT_BUDGET",
            _("Insufficient budget for '{action}'").format(action=action.name),
        )
    return None


def check_target_valid(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """For targeted actions: target must exist, be a Creature, be alive, be at same location."""
    if action.name not in _TARGETED:
        return None

    target_id = action.params.get("target_id") if action.params else None
    if not target_id:
        return None  # no target specified — probes pass, real dispatch relies on handler

    if ctx.get_entity is None:
        return None

    from dnd_simulator.core.character import Creature as CreatureType

    target = ctx.get_entity(str(target_id))
    if not isinstance(target, CreatureType):
        return ValidationError(
            "TARGET_NOT_FOUND",
            _("Target '{id}' not found.").format(id=target_id),
        )

    if not target.is_alive:
        return ValidationError(
            "TARGET_DEAD",
            _("Target '{id}' is already dead.").format(id=target_id),
        )

    if target.location_id != actor.location_id:
        return ValidationError(
            "TARGET_WRONG_LOCATION",
            _("Target '{id}' is not in this region.").format(id=target_id),
        )

    return None


def check_has_item(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """For USE_ITEM/EQUIP: item must exist in actor's inventory."""
    if action.name not in (ActionType.USE_ITEM, ActionType.EQUIP):
        return None

    param_key = "weapon_id" if action.name == ActionType.EQUIP else "item_id"
    item_id = action.params.get(param_key) if action.params else None
    if not item_id:
        return None  # probe — no item specified, skip

    if not any(i.id == str(item_id) for i in actor.inventory):
        return ValidationError(
            "ITEM_NOT_FOUND",
            _("Item '{id}' not in inventory.").format(id=item_id),
        )

    return None


def check_reach(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """For attacks in combat: target must be within weapon reach on the battle map."""
    if action.name != ActionType.ATTACK:
        return None
    if ctx.combat_state is None:
        return None

    target_id = action.params.get("target_id") if action.params else None
    if not target_id:
        return None  # check_target_valid already handles missing target

    from dnd_simulator.core.character import Creature as CreatureType
    from dnd_simulator.rules.movement import grid_distance
    from dnd_simulator.rules.weapons import get_weapon_attack

    # Determine weapon reach
    reach = 5  # default unarmed
    if isinstance(actor, CreatureType):
        reach = get_weapon_attack(actor).reach

    bm = ctx.combat_state.battle_map
    a_pos = bm.get_position(actor.id)
    t_pos = bm.get_position(str(target_id))
    if a_pos is None or t_pos is None:
        return None  # not on map — can't check, let handler deal with it

    dist = grid_distance(a_pos, t_pos)
    if dist > reach:
        return ValidationError(
            "TARGET_OUT_OF_REACH",
            _("Target too far ({dist} ft, reach {reach} ft).").format(dist=dist, reach=reach),
        )

    return None


_CHECKS = [
    check_actor_alive,
    check_actor_active,
    check_action_mode,
    check_budget,
    check_has_item,
    check_target_valid,
    check_reach,
]
