"""Action validation — pure precondition checks before action execution.

No state, no I/O. Takes actor + action + context, returns error or None.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.action_defs import CombatMode, TargetMode, TargetScope, get_action_def
from dnd_simulator.i18n import _
from dnd_simulator.rules.actions import action_cost

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature, Entity
    from dnd_simulator.core.combat import CombatState, Position
    from dnd_simulator.core.turn_budget import TurnBudget


# Type alias for entity lookup — returns Entity or None given an ID.
EntityLookup = Callable[[str], "Entity | None"]

# Callback: (mover, from_pos, to_pos, reactors) → True if mover still alive after reactions.
OnLeaveReachFn = Callable[["Creature", "Position", "Position", "list[Creature]"], bool]


@dataclass(frozen=True)
class ActionContext:
    """Context needed for action validation."""

    is_combat: bool
    current_turn_entity_id: str | None = None  # whose turn (None = outside round)
    turn_budget: TurnBudget | None = None
    combat_state: CombatState | None = None  # for reach checks via BattleMap
    get_entity: EntityLookup | None = field(default=None, repr=False)  # for target validation
    on_leave_reach: OnLeaveReachFn | None = field(default=None, repr=False)  # OA callback


@dataclass(frozen=True)
class ValidationError:
    """Validation failure with machine-readable code and human message."""

    code: str
    message: str


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


def check_required_params(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """All ParamDef entries with required=True must be present in action.params.

    Empty params dict is treated as a probe (availability check) and skipped —
    real dispatches always carry at least one param.
    """
    if not action.params:
        return None
    for p in get_action_def(action.name).params:
        if p.required and p.name not in action.params:
            return ValidationError(
                "MISSING_REQUIRED_PARAM",
                _("'{action}' requires parameter '{param}'.").format(action=action.name, param=p.name),
            )
    return None


def check_action_mode(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """Combat-only actions outside combat and vice versa."""
    d = get_action_def(action.name)
    if ctx.is_combat and d.combat_mode == CombatMode.PEACEFUL_ONLY:
        return ValidationError(
            "WRONG_MODE",
            _("'{action}' is not available in combat").format(action=action.name),
        )
    if not ctx.is_combat and d.combat_mode == CombatMode.COMBAT_ONLY:
        return ValidationError(
            "WRONG_MODE",
            _("'{action}' is not available outside combat").format(action=action.name),
        )
    return None


def check_cost_mode(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """If action carries a cost_mode param, the creature must have a matching cost override."""
    cost_mode = action.params.get("cost_mode") if action.params else None
    if not cost_mode:
        return None

    from dnd_simulator.rules.actions import collect_cost_overrides

    for ov in collect_cost_overrides(actor):
        if ov.action_type == action.name and ov.cost_type.value == str(cost_mode):
            return None

    return ValidationError(
        "INVALID_COST_MODE",
        _("No cost override '{mode}' available for '{action}'").format(mode=cost_mode, action=action.name),
    )


def check_budget(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """Turn budget must cover the action cost."""
    if ctx.turn_budget is None:
        return None
    cost = action_cost(action, creature=actor)
    if not ctx.turn_budget.can_afford(cost):
        return ValidationError(
            "INSUFFICIENT_BUDGET",
            _("Insufficient budget for '{action}'").format(action=action.name),
        )
    return None


def check_target_valid(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """For targeted actions: target must exist, be a Creature, be alive, be at same location."""
    if get_action_def(action.name).target_mode != TargetMode.SINGLE:
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


def check_target_not_full_hp(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """Lay on Hands: refuse when the target is already at full HP."""
    if action.name != ActionType.LAY_ON_HANDS:
        return None
    if not action.params:
        return None  # probe

    from dnd_simulator.core.character import Creature as CreatureType

    target_id = action.params.get("target_id") if action.params else None
    if target_id and ctx.get_entity is not None:
        target_entity = ctx.get_entity(str(target_id))
        target: Creature | None = target_entity if isinstance(target_entity, CreatureType) else None
    else:
        target = actor

    if target is None:
        return None  # other checks will catch missing target

    if target.current_hp >= target.max_hp:
        return ValidationError(
            "TARGET_FULL_HP",
            _("Target is already at full HP."),
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


def check_target_scope(actor: Creature, action: Action, ctx: ActionContext) -> ValidationError | None:
    """For SINGLE-target actions: target must match the action's scope (hostile/ally/any)."""
    ad = get_action_def(action.name)
    if ad.target_mode != TargetMode.SINGLE:
        return None

    target_id = action.params.get("target_id") if action.params else None
    if not target_id:
        return None  # probe mode

    target_id = str(target_id)

    # Self-targeting always allowed for ALLY and ANY scopes
    if target_id == actor.id:
        if ad.target_scope == TargetScope.HOSTILE:
            return ValidationError(
                "WRONG_TARGET_SCOPE",
                _("Cannot target yourself with '{action}'.").format(action=action.name),
            )
        return None

    if ctx.get_entity is None:
        return None

    from dnd_simulator.core.character import Creature as CreatureType

    target = ctx.get_entity(target_id)
    if not isinstance(target, CreatureType):
        return None  # check_target_valid handles missing/non-creature targets

    # Determine hostility via combat sides
    from dnd_simulator.rules.combat_sides import are_allies

    is_hostile: bool | None = None
    if (
        ctx.combat_state
        and ctx.combat_state.entity_to_side
        and actor.id in ctx.combat_state.entity_to_side
        and target_id in ctx.combat_state.entity_to_side
    ):
        is_hostile = not are_allies(ctx.combat_state, actor.id, target_id)

    if is_hostile is None:
        # Outside active combat, a HOSTILE-scope attack is itself the act of
        # becoming hostile — let resolve_attack auto-start combat via
        # forced_opponents. Scope enforcement is only meaningful once sides exist.
        if ctx.combat_state is None and ad.target_scope == TargetScope.HOSTILE:
            return None
        # Fallback to faction comparison — if either has no faction, can't determine
        if not actor.faction_id or not target.faction_id:
            return None  # unknown relation, let it through
        is_hostile = actor.faction_id != target.faction_id

    if ad.target_scope == TargetScope.HOSTILE and not is_hostile:
        return ValidationError(
            "WRONG_TARGET_SCOPE",
            _("'{action}' can only target hostile creatures.").format(action=action.name),
        )
    if ad.target_scope == TargetScope.ALLY and is_hostile:
        return ValidationError(
            "WRONG_TARGET_SCOPE",
            _("'{action}' can only target allies.").format(action=action.name),
        )
    # TargetScope.ANY — always passes
    return None


_CHECKS = [
    check_actor_alive,
    check_actor_active,
    check_required_params,
    check_action_mode,
    check_cost_mode,
    check_budget,
    check_has_item,
    check_target_valid,
    check_target_scope,
    check_target_not_full_hp,
    check_reach,
]
