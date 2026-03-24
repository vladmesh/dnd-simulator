"""Pure functions for D&D 5e condition effects.

No state, no I/O. Takes conditions map in, returns mechanical effects out.
"""

from __future__ import annotations

from dnd_simulator.core.conditions import Condition, ConditionsMap

# Conditions that include the Incapacitated effect (can't take actions/reactions)
_INCAPACITATING: frozenset[Condition] = frozenset(
    {
        Condition.INCAPACITATED,
        Condition.PARALYZED,
        Condition.PETRIFIED,
        Condition.STUNNED,
        Condition.UNCONSCIOUS,
    }
)

# Conditions that set speed to 0
_SPEED_ZERO: frozenset[Condition] = frozenset(
    {
        Condition.GRAPPLED,
        Condition.RESTRAINED,
        Condition.PARALYZED,
        Condition.PETRIFIED,
        Condition.STUNNED,
        Condition.UNCONSCIOUS,
    }
)


def is_incapacitated(conditions: ConditionsMap) -> bool:
    """Creature can't take actions or reactions."""
    return bool(conditions.keys() & _INCAPACITATING)


def effective_speed(base_speed: int, conditions: ConditionsMap) -> int:
    """Compute effective speed after condition modifiers.

    Grappled, Restrained, Paralyzed, Petrified, Stunned, Unconscious → speed 0.
    Prone doesn't reduce speed (standing up costs movement, handled separately).
    """
    if conditions.keys() & _SPEED_ZERO:
        return 0
    return base_speed


def prone_stand_cost(base_speed: int) -> int:
    """Movement cost to stand up from prone: half of speed (D&D 5e rule)."""
    return base_speed // 2


def attacker_has_disadvantage(attacker_conditions: ConditionsMap) -> bool:
    """Does the attacker roll with disadvantage due to their own conditions?

    Blinded, Frightened, Poisoned, Prone, Restrained → disadvantage on attacks.
    """
    return bool(
        attacker_conditions.keys()
        & {
            Condition.BLINDED,
            Condition.FRIGHTENED,
            Condition.POISONED,
            Condition.PRONE,
            Condition.RESTRAINED,
        }
    )


def attacks_against_have_advantage(target_conditions: ConditionsMap, *, melee: bool) -> bool:
    """Do attacks against this target have advantage?

    Blinded, Paralyzed, Petrified, Restrained, Stunned, Unconscious → advantage.
    Prone → advantage for melee, disadvantage for ranged.
    """
    if target_conditions.keys() & {
        Condition.BLINDED,
        Condition.PARALYZED,
        Condition.PETRIFIED,
        Condition.RESTRAINED,
        Condition.STUNNED,
        Condition.UNCONSCIOUS,
    }:
        return True
    return Condition.PRONE in target_conditions and melee


def attacks_against_have_disadvantage(target_conditions: ConditionsMap, *, melee: bool) -> bool:
    """Do attacks against this target have disadvantage?

    Invisible → disadvantage on attacks against.
    Prone → disadvantage for ranged attacks.
    """
    if Condition.INVISIBLE in target_conditions:
        return True
    return Condition.PRONE in target_conditions and not melee


def is_auto_crit(target_conditions: ConditionsMap, *, melee: bool) -> bool:
    """Hits against this target are automatic crits (if they hit).

    Paralyzed, Unconscious → melee hits are auto-crits.
    """
    if not melee:
        return False
    return bool(target_conditions.keys() & {Condition.PARALYZED, Condition.UNCONSCIOUS})


def auto_fail_str_dex_saves(conditions: ConditionsMap) -> bool:
    """Creature auto-fails STR and DEX saving throws.

    Paralyzed, Petrified, Stunned, Unconscious.
    """
    return bool(
        conditions.keys()
        & {
            Condition.PARALYZED,
            Condition.PETRIFIED,
            Condition.STUNNED,
            Condition.UNCONSCIOUS,
        }
    )


def tick_conditions(conditions: ConditionsMap) -> list[Condition]:
    """Decrement timed conditions, remove expired ones. Returns list of removed conditions."""
    expired: list[Condition] = []
    for cond, remaining in list(conditions.items()):
        if remaining is None:
            continue
        if remaining <= 1:
            expired.append(cond)
            del conditions[cond]
        else:
            conditions[cond] = remaining - 1
    return expired
