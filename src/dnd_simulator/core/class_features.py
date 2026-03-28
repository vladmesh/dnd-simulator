"""Class features — composition-based class mechanics.

Each D&D class gets its own frozen dataclass holding class-specific configuration.
Character holds `list[ClassFeatures]` — multiclass gets multiple entries.
Rules in `rules/` consume these; no logic here, pure data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.action_defs import CostOverride, CostType


class FightingStyle(StrEnum):
    """Fighter (and Paladin/Ranger) fighting styles."""

    DEFENSE = "defense"  # +1 AC while wearing armor
    DUELING = "dueling"  # +2 damage with one-handed melee, no weapon in other hand
    GREAT_WEAPON_FIGHTING = "great_weapon_fighting"  # reroll 1-2 on damage dice for two-handed weapons


@dataclass(frozen=True)
class FighterFeatures:
    """Fighter class features (level 1)."""

    fighting_style: FightingStyle
    cost_overrides: tuple[CostOverride, ...] = ()


# Cunning Action: Rogue uses Dash/Disengage as bonus action (PHB p.96)
_CUNNING_ACTION_OVERRIDES: tuple[CostOverride, ...] = (
    CostOverride(ActionType.DASH, CostType.BONUS_ACTION, "cunning_action"),
    CostOverride(ActionType.DISENGAGE, CostType.BONUS_ACTION, "cunning_action"),
)


@dataclass(frozen=True)
class RogueFeatures:
    """Rogue class features (level 1+)."""

    sneak_attack_dice: int = 1  # number of d6; grows every odd level
    cost_overrides: tuple[CostOverride, ...] = field(default=_CUNNING_ACTION_OVERRIDES)


# Union of all class feature types — extend as new classes are implemented.
ClassFeatures = FighterFeatures | RogueFeatures
