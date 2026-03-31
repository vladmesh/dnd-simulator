"""Character creation rules — HP formula, hit dice.

Pure functions, no I/O, no state. D&D 5e SRD rules.
"""

from __future__ import annotations

import math

from dnd_simulator.core.character import CharClass

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
