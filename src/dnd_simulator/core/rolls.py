"""Structured dice result types.

Every dice roll in the system returns one of these types, preserving
individual die faces for UI breakdown and reroll tracking.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DieRoll:
    """One physical die."""

    sides: int  # d6, d8, d20
    result: int  # final kept value
    original: int | None = None  # before reroll (GWF, Halfling Lucky, ...)


@dataclass(frozen=True)
class DiceResult:
    """Structured result of a dice expression like '2d6+3'."""

    expression: str  # "2d6+3"
    dice: tuple[DieRoll, ...]  # each die individually
    flat: int  # +3 part from expression
    total: int  # sum of dice + flat


@dataclass(frozen=True)
class D20Result:
    """d20 roll with advantage/disadvantage tracking."""

    die: DieRoll  # the kept die
    alt: DieRoll | None = None  # the other die if advantage/disadvantage
    advantage: bool = False
    disadvantage: bool = False

    @property
    def natural(self) -> int:
        return self.die.result
