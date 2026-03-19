"""Player character model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dnd_simulator.core.character import (
    Character,
)


@dataclass
class PlayerCharacter(Character):
    """The player's avatar in the world."""

    def to_save_data(self) -> dict[str, Any]:
        """Serialize mutable player state for saving."""
        return {
            "region_id": self.region_id,
            "current_hp": self.current_hp,
            "gold": self.gold,
        }

    def load_save_data(self, data: dict[str, Any]) -> None:
        """Restore mutable state from a save."""
        self.region_id = str(data.get("region_id", self.region_id))
        self.current_hp = int(data.get("current_hp", self.current_hp))
        self.gold = int(data.get("gold", self.gold))
