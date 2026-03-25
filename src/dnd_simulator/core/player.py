"""Player character model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dnd_simulator.core.character import Character
from dnd_simulator.core.items import Item


def _serialize_item(item: Item) -> dict[str, Any]:
    """Serialize an Item to a dict compatible with parse_items()."""
    d: dict[str, Any] = {"id": item.id, "name": item.name, "type": item.item_type.value, **item.params}
    if item.weapon_def:
        w = item.weapon_def
        d["weapon_id"] = w.weapon_id
        d["attack_name"] = w.attack_name
        d["category"] = w.category.value
        d["damage"] = [{"dice": dc.dice, "type": dc.type.value} for dc in w.damage]
        d["reach"] = w.reach
        if w.ability:
            d["ability"] = w.ability.value
        d["modifier"] = w.modifier
        d["is_magic"] = w.is_magic
        d["is_finesse"] = w.is_finesse
        if w.grant_conditions:
            d["grant_conditions"] = [c.value for c in w.grant_conditions]
        if w.grant_actions:
            d["grant_actions"] = [a.value for a in w.grant_actions]
    if item.armor_def:
        a = item.armor_def
        d["armor_id"] = a.armor_id
        d["category"] = a.category.value
        d["base_ac"] = a.base_ac
        d["max_dex_bonus"] = a.max_dex_bonus
    if item.shield_def:
        s = item.shield_def
        d["shield_id"] = s.shield_id
        d["ac_bonus"] = s.ac_bonus
    if item.accessory_def:
        acc = item.accessory_def
        d["accessory_id"] = acc.accessory_id
        d["slot"] = acc.slot.value
        if acc.grant_modifiers:
            d["grant_modifiers"] = [
                {"stat": m.stat.value, "op": m.op.value, "value": m.value, "source": m.source}
                for m in acc.grant_modifiers
            ]
    if item.price is not None:
        d["price"] = item.price
    return d


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
            data["items"] = [_serialize_item(item) for item in self.inventory]
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
