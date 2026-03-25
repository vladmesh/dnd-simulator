"""Abstract squad combat resolution — pure formula, no state, no I/O.

Resolves a squad encountering monsters by comparing squad strength to encounter
power. Used by EcologyLayer when squads move through encounter zones.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TriggeredEncounter:
    """A single encounter entry that was triggered (rolled successfully)."""

    cr: float
    count: int


@dataclass(frozen=True)
class AbstractCombatResult:
    """Outcome of abstract squad vs encounter resolution."""

    won: bool
    strength_lost: int
    encounter_power: float


def resolve_abstract_combat(
    squad_strength: int,
    encounters: list[TriggeredEncounter],
) -> AbstractCombatResult:
    """Resolve squad vs encounters by strength comparison.

    Formula:
    - encounter_power = sum(cr * count) for each triggered entry
    - squad wins if strength >= encounter_power
    - winner loses ceil(encounter_power / 2) strength
    - loser loses ceil(own_strength / 2) strength (retreat)
    - strength loss capped at current strength (can't go below 0)
    """
    encounter_power = sum(e.cr * e.count for e in encounters)

    if not encounters or encounter_power == 0.0:
        return AbstractCombatResult(won=True, strength_lost=0, encounter_power=0.0)

    won = squad_strength >= encounter_power

    if won:
        strength_lost = min(math.ceil(encounter_power / 2), squad_strength)
    else:
        strength_lost = min(math.ceil(squad_strength / 2), squad_strength)

    return AbstractCombatResult(won=won, strength_lost=strength_lost, encounter_power=encounter_power)
