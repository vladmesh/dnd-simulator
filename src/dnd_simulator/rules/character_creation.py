"""Character creation rules — HP formula, hit dice.

Pure functions, no I/O, no state. D&D 5e SRD rules.
"""

from __future__ import annotations

import math

from dnd_simulator.core.character import Ability, CharClass
from dnd_simulator.core.class_features import FightingStyle

# Hit die size per class (only Fighter and Rogue implemented).
HIT_DICE: dict[CharClass, int] = {
    CharClass.FIGHTER: 10,
    CharClass.ROGUE: 8,
}


def calculate_max_hp(char_class: CharClass, level: int, con_modifier: int) -> int:
    """Calculate max HP using D&D 5e formula.

    Level 1: max hit die + CON modifier (minimum 1 total).
    Higher levels: L1 HP + (level-1) x (die_avg_rounded_up + CON mod, min 1 per level).
    """
    if level < 1:
        raise RuntimeError(f"level must be >= 1, got {level}")

    hit_die = HIT_DICE.get(char_class)
    if hit_die is None:
        raise RuntimeError(f"No hit die defined for {char_class.value}")

    # Level 1: max hit die + CON mod, minimum 1 total
    l1_hp = max(hit_die + con_modifier, 1)

    if level == 1:
        return l1_hp

    # Higher levels: average hit die (rounded up) + CON mod per level, min 1
    die_avg = math.ceil(hit_die / 2) + 1  # e.g. d10 → 6, d8 → 5
    hp_per_level = max(die_avg + con_modifier, 1)

    return l1_hp + (level - 1) * hp_per_level


# D&D 5e point buy cost table: score -> point cost.
POINT_BUY_COSTS: dict[int, int] = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 7,
    15: 9,
}

POINT_BUY_BUDGET = 27


def validate_point_buy(scores: dict[Ability, int]) -> None:
    """Validate a point buy ability score allocation.

    Raises ValueError if scores are invalid (missing abilities, out of range, over budget).
    """
    missing = set(Ability) - set(scores)
    if missing:
        names = ", ".join(sorted(a.value for a in missing))
        raise ValueError(f"Missing abilities: {names}")

    for ability, score in scores.items():
        if score < 8 or score > 15:
            raise ValueError(f"{ability.value} score {score} out of range [8, 15]")

    total_cost = sum(POINT_BUY_COSTS[score] for score in scores.values())
    if total_cost > POINT_BUY_BUDGET:
        raise ValueError(f"Point buy cost {total_cost} exceeds budget of {POINT_BUY_BUDGET}")


STARTING_GOLD = 100

# Starting equipment per class — item catalog ref IDs.
_STARTING_EQUIPMENT: dict[CharClass, list[str]] = {
    CharClass.FIGHTER: ["chain_mail", "longsword", "shield"],
    CharClass.ROGUE: ["leather", "rapier", "shortbow", "dagger"],
}

# GWF fighters get a greatsword instead of longsword + shield.
_FIGHTER_GWF_EQUIPMENT: list[str] = ["chain_mail", "greatsword"]


def starting_equipment(char_class: CharClass, fighting_style: FightingStyle | None = None) -> list[str]:
    """Return starting equipment item refs for a class. Returns a copy."""
    if char_class == CharClass.FIGHTER and fighting_style == FightingStyle.GREAT_WEAPON_FIGHTING:
        return list(_FIGHTER_GWF_EQUIPMENT)
    items = _STARTING_EQUIPMENT.get(char_class)
    if items is None:
        raise RuntimeError(f"No starting equipment defined for {char_class.value}")
    return list(items)
