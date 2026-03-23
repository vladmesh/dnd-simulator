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
        data: dict[str, Any] = {
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
        if self.inventory:
            data["items"] = [
                {"id": item.id, "name": item.name, "type": item.item_type.value, **item.params}
                for item in self.inventory
            ]
        return data

    def load_save_data(self, data: dict[str, Any]) -> None:
        """Restore mutable state from a save."""
        from dnd_simulator.core.items import Item, ItemType

        self.location_id = str(data.get("location_id", data.get("region_id", self.location_id)))
        self.current_hp = int(data.get("current_hp", self.current_hp))
        self.gold = int(data.get("gold", self.gold))
        items_data = data.get("items")
        if isinstance(items_data, list):
            self.inventory = [
                Item(
                    id=str(d["id"]),
                    name=str(d["name"]),
                    item_type=ItemType(d["type"]),
                    params={k: v for k, v in d.items() if k not in ("id", "name", "type")},
                )
                for d in items_data
            ]
