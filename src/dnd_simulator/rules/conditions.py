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


def is_incapacitated(conditions: ConditionsMap) -> bool:
    """Creature can't take actions or reactions."""
    return bool(conditions.keys() & _INCAPACITATING)


def prone_stand_cost(base_speed: int) -> int:
    """Movement cost to stand up from prone: half of speed (D&D 5e rule)."""
    return base_speed // 2


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
