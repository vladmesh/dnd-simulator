"""Player character model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dnd_simulator.core.character import Character


@dataclass
class PlayerCharacter(Character):
    """The player's avatar in the world.

    Decisions are made by an attached Brain (PlayerBrain), just like NPCs.
    Transport-specific I/O (CLI, WebSocket) is handled by the Brain's turn handler.
    """

    def to_save_data(self) -> dict[str, Any]:
        """Serialize mutable player state for saving."""
        return {
            "location_id": self.location_id,
            "current_hp": self.current_hp,
            "gold": self.gold,
        }

    def to_full_save_data(self) -> dict[str, Any]:
        """Serialize full player definition (for autosave restore)."""
        return {
            "name": self.name,
            "race": self.race.value,
            "class": self.char_class.value,
            "level": self.level,
            "alignment": self.alignment.value,
            "appearance": self.appearance,
            "ability_scores": {a.value: s for a, s in self.ability_scores.scores.items()},
            "hp": self.max_hp,
            "ac": self.ac,
            "gold": self.gold,
            "start_location": self.location_id,
            "current_hp": self.current_hp,
        }

    def load_save_data(self, data: dict[str, Any]) -> None:
        """Restore mutable state from a save."""
        self.location_id = str(data.get("location_id", data.get("region_id", self.location_id)))
        self.current_hp = int(data.get("current_hp", self.current_hp))
        self.gold = int(data.get("gold", self.gold))
