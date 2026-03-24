"""Dice rolling — the atomic building block of D&D mechanics.

All functions accept an optional ``rng`` (random.Random instance) for
deterministic testing.  When omitted, the module-level RNG is used.
"""

from __future__ import annotations

import os
import random
import re

_seed_env = os.environ.get("DND_DICE_SEED")
_rng = random.Random(int(_seed_env)) if _seed_env is not None else random.Random()

# Pattern: "2d6", "1d8+3", "2d6-1", "4" (constant)
_DICE_RE = re.compile(r"^(?:(\d+)d(\d+))?\s*([+-]?\s*\d+)?$", re.IGNORECASE)


def roll_d20(*, advantage: bool = False, disadvantage: bool = False, rng: random.Random | None = None) -> int:
    """Roll a d20, optionally with advantage or disadvantage."""
    r = rng or _rng
    first = r.randint(1, 20)
    if advantage and not disadvantage:
        return max(first, r.randint(1, 20))
    if disadvantage and not advantage:
        return min(first, r.randint(1, 20))
    return first


def roll(expr: str, *, rng: random.Random | None = None) -> int:
    """Evaluate a dice expression like ``'2d6+3'``, ``'1d8'``, or ``'4'``.

    Returns the total.  Raises ``ValueError`` on malformed input.
    """
    expr = expr.strip()
    m = _DICE_RE.match(expr)
    if not m:
        raise ValueError(f"Invalid dice expression: {expr!r}")

    r = rng or _rng
    total = 0

    if m.group(1) and m.group(2):
        count = int(m.group(1))
        sides = int(m.group(2))
        if count < 1 or sides < 1:
            raise ValueError(f"Invalid dice expression: {expr!r}")
        for _ in range(count):
            total += r.randint(1, sides)

    if m.group(3):
        total += int(m.group(3).replace(" ", ""))

    return total
