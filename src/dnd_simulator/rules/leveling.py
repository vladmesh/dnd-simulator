"""Pure leveling rules: XP-by-CR (DMG p.275) and level thresholds (PHB p.15)."""

from typing import Final

_XP_BY_CR: Final[dict[float, int]] = {
    0.0: 10,
    0.125: 25,
    0.25: 50,
    0.5: 100,
    1.0: 200,
    2.0: 450,
    3.0: 700,
    4.0: 1100,
    5.0: 1800,
    6.0: 2300,
    7.0: 2900,
    8.0: 3900,
    9.0: 5000,
    10.0: 5900,
}

_XP_THRESHOLDS: Final[tuple[int, ...]] = (
    0,
    300,
    900,
    2700,
    6500,
    14000,
    23000,
    34000,
    48000,
    64000,
    85000,
    100000,
    120000,
    140000,
    165000,
    195000,
    225000,
    265000,
    305000,
    355000,
)

MAX_LEVEL: Final[int] = 20


def xp_for_cr(cr: float) -> int:
    key = float(cr)
    if key not in _XP_BY_CR:
        raise ValueError(f"CR {cr} not in XP table")
    return _XP_BY_CR[key]


def level_for_xp(xp: int) -> int:
    for level in range(MAX_LEVEL, 0, -1):
        if xp >= _XP_THRESHOLDS[level - 1]:
            return level
    return 1


def xp_to_next_level(xp: int) -> int:
    current = level_for_xp(xp)
    if current >= MAX_LEVEL:
        return 0
    return _XP_THRESHOLDS[current] - xp


def can_level_up(xp: int, current_level: int) -> bool:
    return current_level < MAX_LEVEL and level_for_xp(xp) > current_level
