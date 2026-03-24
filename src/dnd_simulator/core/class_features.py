"""Class features — composition-based class mechanics.

Each D&D class gets its own frozen dataclass holding class-specific configuration.
Character holds `list[ClassFeatures]` — multiclass gets multiple entries.
Rules in `rules/` consume these; no logic here, pure data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FightingStyle(StrEnum):
    """Fighter (and Paladin/Ranger) fighting styles."""

    DEFENSE = "defense"  # +1 AC while wearing armor
    DUELING = "dueling"  # +2 damage with one-handed melee, no weapon in other hand


@dataclass(frozen=True)
class FighterFeatures:
    """Fighter class features (level 1)."""

    fighting_style: FightingStyle


@dataclass(frozen=True)
class RogueFeatures:
    """Rogue class features (level 1+)."""

    sneak_attack_dice: int = 1  # number of d6; grows every odd level


# Union of all class feature types — extend as new classes are implemented.
ClassFeatures = FighterFeatures | RogueFeatures
