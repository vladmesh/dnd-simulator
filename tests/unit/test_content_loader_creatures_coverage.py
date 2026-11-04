"""Coverage for NPC location validation and player inventory/equipment restoration."""

from __future__ import annotations

from dataclasses import replace

import pytest

from dnd_simulator.content_loader.creatures import load_player_save_data, parse_npc, parse_player
from dnd_simulator.core.items import EquipmentSlot, Item, ItemType


@pytest.mark.parametrize(
    ("known_locations", "known_message"),
    [
        (set(), r"\[\]"),
        ({"tavern", "castle_gate"}, r"\['castle_gate', 'tavern'\]"),
    ],
)
def test_npc_rejects_unknown_start_location(known_locations: set[str], known_message: str) -> None:
    with pytest.raises(
        RuntimeError,
        match=(
            r"^NPC 'guard' has start_location 'missing' which is not a known location\. "
            rf"Known: {known_message}$"
        ),
    ):
        parse_npc(
            "guard",
            {"name": {"en": "Guard"}, "start_location": "missing"},
            known_locations=known_locations,
        )


def test_load_player_save_replaces_inventory_and_preserves_item_ids() -> None:
    player = parse_player(
        {
            "id": "player_test",
            "name": {"en": "Hero"},
            "items": [{"name": "Old Potion", "type": "potion", "heal_dice": "1d4"}],
        }
    )

    load_player_save_data(
        player,
        {
            "items": [
                {"id": "potion_42", "name": "Health Potion", "type": "potion", "heal_dice": "2d4+2"},
                {"id": "potion_43", "name": "Health Potion", "type": "potion", "heal_dice": "2d4+2"},
            ]
        },
    )

    assert player.inventory == [
        Item(id="potion_42", name="Health Potion", item_type=ItemType.POTION, params={"heal_dice": "2d4+2"}),
        Item(id="potion_43", name="Health Potion", item_type=ItemType.POTION, params={"heal_dice": "2d4+2"}),
    ]

    load_player_save_data(player, {"items": []})

    assert player.inventory == []


@pytest.mark.parametrize(
    ("slot", "item_data"),
    [
        (
            EquipmentSlot.WEAPON,
            {
                "name": "Longsword",
                "type": "weapon",
                "weapon_id": "longsword",
                "category": "martial",
                "attack_name": "longsword strike",
                "damage": [{"dice": "1d8", "type": "slashing"}],
            },
        ),
        (
            EquipmentSlot.ARMOR,
            {"name": "Chain Mail", "type": "armor", "armor_id": "chain_mail", "category": "heavy", "base_ac": 16},
        ),
        (
            EquipmentSlot.SHIELD,
            {"name": "Shield", "type": "shield", "shield_id": "shield", "ac_bonus": 2},
        ),
        *[
            (
                slot,
                {
                    "name": f"Protective {slot.value}",
                    "type": "accessory",
                    "accessory_id": f"protective_{slot.value}",
                    "slot": slot.value,
                    "modifiers": [{"stat": "ac", "op": "add", "value": 1, "source": f"protective_{slot.value}"}],
                },
            )
            for slot in (EquipmentSlot.HEAD, EquipmentSlot.FEET, EquipmentSlot.RING)
        ],
    ],
)
def test_load_player_save_restores_legacy_equipment(slot: EquipmentSlot, item_data: dict[str, object]) -> None:
    source = parse_player({"id": "player_test", "name": {"en": "Hero"}, "items": [item_data]})
    restored = parse_player({"id": "player_test", "name": {"en": "Hero"}})

    load_player_save_data(restored, {f"equipped_{slot.value}": {**item_data, "id": "saved_equipment_42"}})

    assert restored.equipped == {slot: replace(source.inventory[0], id="saved_equipment_42")}
    assert restored.inventory == []
