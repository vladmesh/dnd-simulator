"""Combat state — tracks initiative order and round progression for a fight."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CombatState:
    """Active combat in a region.

    Tracks turn order (by initiative), round counter, and
    rounds-without-attack for automatic combat exit.
    """

    region_id: str
    turn_order: list[str] = field(default_factory=list)  # entity IDs in initiative order
    round_number: int = 1
    rounds_without_attack: int = 0
