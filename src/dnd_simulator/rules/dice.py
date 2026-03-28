"""Dice rolling — the atomic building block of D&D mechanics.

All functions accept an optional ``rng`` (random.Random instance) for
deterministic testing.  When omitted, the module-level RNG is used.
"""

from __future__ import annotations

import os
import random
import re

from dnd_simulator.core.rolls import D20Result, DiceResult, DieRoll

_seed_env = os.environ.get("DND_DICE_SEED")
_rng = random.Random(int(_seed_env)) if _seed_env is not None else random.Random()

# Pattern: "2d6", "1d8+3", "2d6-1", "4" (constant)
_DICE_RE = re.compile(r"^(?:(\d+)d(\d+))?\s*([+-]?\s*\d+)?$", re.IGNORECASE)


def roll_d20(*, advantage: bool = False, disadvantage: bool = False, rng: random.Random | None = None) -> D20Result:
    """Roll a d20, optionally with advantage or disadvantage."""
    r = rng or _rng

    if advantage and disadvantage:
        # Cancel out — straight roll
        value = r.randint(1, 20)
        return D20Result(die=DieRoll(sides=20, result=value))

    first = r.randint(1, 20)

    if advantage:
        second = r.randint(1, 20)
        if first >= second:
            return D20Result(
                die=DieRoll(sides=20, result=first),
                alt=DieRoll(sides=20, result=second),
                advantage=True,
            )
        return D20Result(
            die=DieRoll(sides=20, result=second),
            alt=DieRoll(sides=20, result=first),
            advantage=True,
        )

    if disadvantage:
        second = r.randint(1, 20)
        if first <= second:
            return D20Result(
                die=DieRoll(sides=20, result=first),
                alt=DieRoll(sides=20, result=second),
                disadvantage=True,
            )
        return D20Result(
            die=DieRoll(sides=20, result=second),
            alt=DieRoll(sides=20, result=first),
            disadvantage=True,
        )

    return D20Result(die=DieRoll(sides=20, result=first))


def roll(expr: str, *, reroll_below: int = 0, rng: random.Random | None = None) -> DiceResult:
    """Evaluate a dice expression like ``'2d6+3'``, ``'1d8'``, or ``'4'``.

    Returns a ``DiceResult`` with individual die faces.
    ``reroll_below``: each die showing <= threshold is rerolled once (GWF-style).
    Raises ``ValueError`` on malformed input.
    """
    expr = expr.strip()
    m = _DICE_RE.match(expr)
    if not m:
        raise ValueError(f"Invalid dice expression: {expr!r}")

    r = rng or _rng
    dice: list[DieRoll] = []

    if m.group(1) and m.group(2):
        count = int(m.group(1))
        sides = int(m.group(2))
        if count < 0 or sides < 1:
            raise ValueError(f"Invalid dice expression: {expr!r}")
        for _ in range(count):
            value = r.randint(1, sides)
            if reroll_below > 0 and value <= reroll_below:
                original = value
                value = r.randint(1, sides)
                dice.append(DieRoll(sides=sides, result=value, original=original))
            else:
                dice.append(DieRoll(sides=sides, result=value))

    flat = 0
    if m.group(3):
        flat = int(m.group(3).replace(" ", ""))

    total = sum(d.result for d in dice) + flat
    return DiceResult(expression=expr, dice=tuple(dice), flat=flat, total=total)
