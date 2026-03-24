"""Modifier pipeline data types for derived stats computation.

Modifiers represent effects on creature stats from conditions, equipment, spells,
and class features. The pipeline collects modifiers from all sources and computes
effective stat values.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModifierOp(Enum):
    """How a modifier affects a stat."""

    ADD = "add"  # flat +N / -N
    OVERRIDE = "override"  # force final value (e.g. speed=0 from grapple)
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


class StatType(Enum):
    """What stat a modifier targets."""

    AC = "ac"
    SPEED = "speed"
    ATTACK_ROLL = "attack_roll"
    INITIATIVE = "initiative"
    DAMAGE = "damage"


@dataclass(frozen=True)
class Modifier:
    """A single modifier from any source (condition, equipment, spell, etc.).

    Same ``source`` string = don't stack (D&D 5e: same-named effects).
    ``melee_only`` / ``ranged_only`` for context-dependent modifiers (Prone).
    ``dice`` for probabilistic bonuses rolled at resolution time (Bless +1d4).
    """

    stat: StatType
    op: ModifierOp
    value: int = 0
    dice: str = ""
    source: str = ""
    melee_only: bool = False
    ranged_only: bool = False


@dataclass(frozen=True)
class RollComponent:
    """One labeled component of a d20 roll or damage total."""

    source: str  # "ability", "proficiency", "bless", "weapon_magic", "dueling"
    value: int  # already-resolved numeric value
    dice: str = ""  # original dice expression if rolled (display only)


@dataclass(frozen=True)
class AttackModifiers:
    """Pre-computed attack parameters for combat_manager.resolve_attack()."""

    modifier: int
    damage_bonus: int
    dice_bonuses: tuple[str, ...]
    advantage: bool
    disadvantage: bool
    force_crit: bool
    target_ac: int
    roll_components: tuple[RollComponent, ...] = ()
    damage_components: tuple[RollComponent, ...] = ()
