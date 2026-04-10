"""Tests for starting equipment persistence — weapon must survive save/load and combat.

Bug: Player created with correct AC (armor+shield) but fights with "fists" in combat.
The weapon is set at creation but lost during save/load or somewhere before combat.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_simulator.content_loader import parse_player
from dnd_simulator.content_loader.items import deserialize_item
from dnd_simulator.content_loader.schemas import ItemContent
from dnd_simulator.core.items import ItemType
from dnd_simulator.core.player import _EQUIPMENT_FIELDS, PlayerCharacter, _serialize_item
from dnd_simulator.rules.weapons import get_weapon_attack


def _load_item_catalog() -> dict[str, ItemContent]:
    """Load the real item catalog from content/catalogs/items/."""
    from dnd_simulator.content_loader.catalogs import load_catalog

    catalog_dir = Path(__file__).resolve().parents[2] / "content" / "catalogs" / "items"
    return load_catalog(catalog_dir, ItemContent)


def _create_fighter(item_catalog: dict[str, ItemContent]) -> PlayerCharacter:
    """Create a standard fighter with starting equipment via parse_player."""
    parse_data: dict[str, Any] = {
        "name": "Test Fighter",
        "race": "human",
        "class": "fighter",
        "level": 1,
        "alignment": "true_neutral",
        "hp": 12,
        "ac": 10,
        "gold": 100,
        "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
        "items": [
            {"ref": "chain_mail", "equipped": True},
            {"ref": "longsword", "equipped": True},
            {"ref": "shield", "equipped": True},
        ],
        "class_features": {"fighting_style": "defense"},
    }
    return parse_player(parse_data, item_catalog=item_catalog)


class TestStartingEquipmentAfterCreation:
    """Equipment slots are set correctly after parse_player."""

    def test_fighter_has_equipped_weapon(self) -> None:
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)
        assert player.equipped_weapon is not None, "Longsword should be equipped"
        assert player.equipped_weapon.item_type == ItemType.WEAPON
        assert player.equipped_weapon.weapon_def is not None
        assert player.equipped_weapon.weapon_def.attack_name == "longsword slash"

    def test_fighter_has_equipped_armor(self) -> None:
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)
        assert player.equipped_armor is not None, "Chain mail should be equipped"
        assert player.equipped_armor.armor_def is not None

    def test_fighter_has_equipped_shield(self) -> None:
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)
        assert player.equipped_shield is not None, "Shield should be equipped"
        assert player.equipped_shield.shield_def is not None

    def test_get_weapon_attack_returns_longsword(self) -> None:
        """get_weapon_attack must return the longsword, not fists."""
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)
        attack = get_weapon_attack(player)
        assert attack.name == "longsword slash", f"Expected 'longsword slash', got '{attack.name}'"
        assert attack.damage[0].dice == "1d8"


class TestEquipmentRoundTripSerialization:
    """Equipment survives _serialize_item → deserialize_item."""

    def test_weapon_round_trip(self) -> None:
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)
        weapon = player.equipped_weapon
        assert weapon is not None

        serialized = _serialize_item(weapon)
        restored = deserialize_item(serialized)

        assert restored.item_type == ItemType.WEAPON
        assert restored.weapon_def is not None
        assert restored.weapon_def.attack_name == "longsword slash"
        assert restored.weapon_def.damage[0].dice == "1d8"

    def test_armor_round_trip(self) -> None:
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)
        armor = player.equipped_armor
        assert armor is not None

        serialized = _serialize_item(armor)
        restored = deserialize_item(serialized)

        assert restored.item_type == ItemType.ARMOR
        assert restored.armor_def is not None
        assert restored.armor_def.base_ac == 16


class TestPlayerFullSaveRestore:
    """to_full_save_data → parse_player round-trip preserves equipment."""

    def test_full_save_restore_preserves_weapon(self) -> None:
        """The critical bug: weapon must survive to_full_save_data → parse_player."""
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)

        # Verify original has weapon
        assert player.equipped_weapon is not None

        # Save
        save_data = player.to_full_save_data()

        # Restore via parse_player (same path as load_state for new players)
        restored = parse_player(save_data, item_catalog=catalog)

        assert restored.equipped_weapon is not None, (
            "Weapon lost after save/restore! "
            f"Save data keys: {list(save_data.keys())}, "
            f"'equipped_weapon' in save: {'equipped_weapon' in save_data}"
        )
        assert restored.equipped_weapon.weapon_def is not None
        assert restored.equipped_weapon.weapon_def.attack_name == "longsword slash"

    def test_full_save_restore_preserves_armor_and_shield(self) -> None:
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)

        save_data = player.to_full_save_data()
        restored = parse_player(save_data, item_catalog=catalog)

        assert restored.equipped_armor is not None, "Armor lost after save/restore"
        assert restored.equipped_shield is not None, "Shield lost after save/restore"

    def test_get_weapon_attack_after_restore(self) -> None:
        """get_weapon_attack must return longsword after save/restore, not fists."""
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)

        save_data = player.to_full_save_data()
        restored = parse_player(save_data, item_catalog=catalog)

        attack = get_weapon_attack(restored)
        assert attack.name == "longsword slash", f"Expected 'longsword slash' after restore, got '{attack.name}'"


class TestEntitiesLayerSaveRestore:
    """Equipment survives entities layer get_state → load_state cycle."""

    def test_player_equipment_survives_layer_save_load(self) -> None:
        """Simulate the entities layer save/load path for a player character."""
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)

        # Simulate get_state serialization (what entities layer does)
        edata: dict[str, Any] = {"entity_type": "player"}
        # Creature-level equipment serialization
        for field_name in _EQUIPMENT_FIELDS:
            eq_item = getattr(player, field_name)
            if eq_item is not None:
                edata[field_name] = _serialize_item(eq_item)
        # Player-level full save
        edata.update(player.to_full_save_data())

        # Simulate load_state: parse_player path (entity doesn't exist in template)
        restored = parse_player(edata)
        restored.current_hp = int(edata.get("current_hp", restored.max_hp))

        # This is what the load_state code does AFTER parse_player if it
        # falls through (like NPCs do). But for players it does `continue`.
        # Without the fallthrough, equipment is lost:
        assert restored.equipped_weapon is not None, (
            "Weapon lost in entities layer save/load! The `continue` after parse_player skips equipment restoration."
        )

        attack = get_weapon_attack(restored)
        assert attack.name == "longsword slash", f"Expected 'longsword slash', got '{attack.name}'"
