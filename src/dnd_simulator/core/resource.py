"""Resource pools — trackable per-creature resources (Second Wind, spell slots, etc.)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RestType(StrEnum):
    """When a resource pool resets."""

    SHORT_REST = "short_rest"
    LONG_REST = "long_rest"


@dataclass
class ResourcePool:
    """A single trackable resource with max uses and rest-based reset.

    Examples: Second Wind (1/short rest), Action Surge (1/short rest),
    spell slots (N/long rest), Hit Dice (level/long rest).
    """

    id: str  # "second_wind", "action_surge", "spell_slot_1"
    max_uses: int
    current_uses: int
    reset_on: RestType

    def __post_init__(self) -> None:
        if self.max_uses < 1:
            raise ValueError(f"ResourcePool {self.id}: max_uses must be >= 1, got {self.max_uses}")
        if self.current_uses < 0 or self.current_uses > self.max_uses:
            raise ValueError(
                f"ResourcePool {self.id}: current_uses must be 0..{self.max_uses}, got {self.current_uses}"
            )
