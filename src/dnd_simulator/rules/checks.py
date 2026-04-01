"""Core D&D check mechanics — attack rolls, ability checks, saving throws.

Every check in D&D boils down to: d20 + modifier vs DC (or AC).
These three functions cover all of them.  Pure, stateless, no side effects.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from dnd_simulator.core.rolls import D20Result, DieRoll
from dnd_simulator.rules.dice import roll, roll_d20

_PLACEHOLDER_D20 = D20Result(die=DieRoll(sides=20, result=0))


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a d20-based check."""

    success: bool
    roll: int  # natural d20 result
    total: int  # roll + modifier
    dc: int  # what we were rolling against
    critical: bool  # nat 20 (hit) or nat 1 (miss)
    d20: D20Result = _PLACEHOLDER_D20


def attack_roll(
    modifier: int,
    ac: int,
    *,
    advantage: bool = False,
    disadvantage: bool = False,
    rng: random.Random | None = None,
) -> CheckResult:
    """d20 + modifier vs AC.  Nat 20 always hits, nat 1 always misses."""
    d20_result = roll_d20(advantage=advantage, disadvantage=disadvantage, rng=rng)
    d20 = d20_result.natural
    total = d20 + modifier
    if d20 == 20:
        return CheckResult(success=True, roll=d20, total=total, dc=ac, critical=True, d20=d20_result)
    if d20 == 1:
        return CheckResult(success=False, roll=d20, total=total, dc=ac, critical=True, d20=d20_result)
    return CheckResult(success=d20 + modifier >= ac, roll=d20, total=total, dc=ac, critical=False, d20=d20_result)


def ability_check(
    modifier: int,
    dc: int,
    *,
    advantage: bool = False,
    disadvantage: bool = False,
    rng: random.Random | None = None,
) -> CheckResult:
    """d20 + modifier vs DC.  No critical hits/misses on ability checks (RAW)."""
    d20_result = roll_d20(advantage=advantage, disadvantage=disadvantage, rng=rng)
    d20 = d20_result.natural
    return CheckResult(
        success=d20 + modifier >= dc, roll=d20, total=d20 + modifier, dc=dc, critical=False, d20=d20_result
    )


def saving_throw(
    modifier: int,
    dc: int,
    *,
    advantage: bool = False,
    disadvantage: bool = False,
    rng: random.Random | None = None,
) -> CheckResult:
    """d20 + modifier vs DC.  Same as ability_check mechanically."""
    return ability_check(modifier, dc, advantage=advantage, disadvantage=disadvantage, rng=rng)


def damage_roll(expr: str, *, critical: bool = False, rng: random.Random | None = None) -> int:
    """Roll damage dice.  On a critical hit, multiply dice total by 2 (not the modifier)."""
    result = roll(expr, rng=rng)
    if not critical or not result.dice:
        return result.total
    dice_sum = sum(d.result for d in result.dice)
    return dice_sum * 2 + result.flat
