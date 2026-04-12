"""Class features — composition-based class mechanics.

Each D&D class gets its own frozen dataclass holding class-specific configuration.
Character holds `list[ClassFeatures]` — multiclass gets multiple entries.
Rules in `rules/` consume these; no logic here, pure data + thin delegation to
shared helpers in ``rules/`` (lazy-imported to keep ``core`` free of runtime
dependencies on ``rules``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.action_defs import CostOverride, CostType

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.modifiers import AttackContribution, Modifier


class FightingStyle(StrEnum):
    """Fighter (and Paladin/Ranger) fighting styles."""

    DEFENSE = "defense"  # +1 AC while wearing armor
    DUELING = "dueling"  # +2 damage with one-handed melee, no weapon in other hand
    GREAT_WEAPON_FIGHTING = "great_weapon_fighting"  # reroll 1-2 on damage dice for two-handed weapons


def _fighting_style_self_modifiers(style: FightingStyle | None, creature: Creature) -> list[Modifier]:
    from dnd_simulator.rules.fighting_style import self_modifiers_for_style

    return self_modifiers_for_style(style, creature)


def _fighting_style_attack_contribution(
    style: FightingStyle | None, creature: Creature, *, melee: bool
) -> AttackContribution:
    from dnd_simulator.rules.fighting_style import attack_contribution_for_style

    return attack_contribution_for_style(style, creature, melee=melee)


def _empty_attack_contribution() -> AttackContribution:
    from dnd_simulator.core.modifiers import AttackContribution

    return AttackContribution()


@dataclass(frozen=True)
class FighterFeatures:
    """Fighter class features (level 1)."""

    fighting_style: FightingStyle
    cost_overrides: tuple[CostOverride, ...] = ()

    def collect_self_modifiers(self, creature: Creature) -> list[Modifier]:
        return _fighting_style_self_modifiers(self.fighting_style, creature)

    def collect_attack_modifiers(self, creature: Creature, *, melee: bool) -> AttackContribution:
        return _fighting_style_attack_contribution(self.fighting_style, creature, melee=melee)


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

    def collect_self_modifiers(self, creature: Creature) -> list[Modifier]:
        return []

    def collect_attack_modifiers(self, creature: Creature, *, melee: bool) -> AttackContribution:
        return _empty_attack_contribution()


@dataclass(frozen=True)
class PaladinFeatures:
    """Paladin class features (level 1+)."""

    fighting_style: FightingStyle | None = None
    cost_overrides: tuple[CostOverride, ...] = ()

    def collect_self_modifiers(self, creature: Creature) -> list[Modifier]:
        return _fighting_style_self_modifiers(self.fighting_style, creature)

    def collect_attack_modifiers(self, creature: Creature, *, melee: bool) -> AttackContribution:
        return _fighting_style_attack_contribution(self.fighting_style, creature, melee=melee)


# Union of all class feature types — extend as new classes are implemented.
ClassFeatures = FighterFeatures | RogueFeatures | PaladinFeatures
