"""Tests for starting equipment persistence — weapon must survive save/load and combat.

Bug: Player created with correct AC (armor+shield) but fights with "fists" in combat.
The weapon is set at creation but lost during save/load or somewhere before combat.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dnd_simulator.content_loader import parse_player, player_to_full_save_data
from dnd_simulator.content_loader.catalogs import load_catalog
from dnd_simulator.content_loader.items import EQUIPMENT_FIELDS, deserialize_item, serialize_item
from dnd_simulator.content_loader.schemas import ItemContent
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle, PaladinFeatures, RogueFeatures
from dnd_simulator.core.items import ItemType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.rules.modifiers import effective_ac
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
        "gold": 1000,
        "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
        "items": [
            {"ref": "chain_mail", "equipped": True},
            {"ref": "longsword", "equipped": True},
            {"ref": "shield", "equipped": True},
        ],
        "class_features": {"fighting_style": "defense"},
    }
    return parse_player(parse_data, item_catalog=item_catalog)


def _create_rogue(item_catalog: dict[str, ItemContent]) -> PlayerCharacter:
    """Create a standard rogue with starting equipment via parse_player."""
    parse_data: dict[str, Any] = {
        "name": "Test Rogue",
        "race": "human",
        "class": "rogue",
        "level": 1,
        "alignment": "true_neutral",
        "hp": 10,
        "ac": 10,
        "gold": 1000,
        "ability_scores": {"str": 8, "dex": 15, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "items": [
            {"ref": "leather", "equipped": True},
            {"ref": "rapier", "equipped": True},
        ],
    }
    return parse_player(parse_data, item_catalog=item_catalog)


def _create_paladin(item_catalog: dict[str, ItemContent]) -> PlayerCharacter:
    """Create a standard paladin with starting equipment via parse_player."""
    parse_data: dict[str, Any] = {
        "name": "Test Paladin",
        "race": "human",
        "class": "paladin",
        "level": 1,
        "alignment": "lawful_good",
        "hp": 12,
        "ac": 10,
        "gold": 1000,
        "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
        "items": [
            {"ref": "chain_mail", "equipped": True},
            {"ref": "longsword", "equipped": True},
            {"ref": "shield", "equipped": True},
        ],
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

        serialized = serialize_item(weapon)
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

        serialized = serialize_item(armor)
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
        save_data = player_to_full_save_data(player)

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

        save_data = player_to_full_save_data(player)
        restored = parse_player(save_data, item_catalog=catalog)

        assert restored.equipped_armor is not None, "Armor lost after save/restore"
        assert restored.equipped_shield is not None, "Shield lost after save/restore"

    def test_get_weapon_attack_after_restore(self) -> None:
        """get_weapon_attack must return longsword after save/restore, not fists."""
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)

        save_data = player_to_full_save_data(player)
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
        for field_name in EQUIPMENT_FIELDS:
            eq_item = getattr(player, field_name)
            if eq_item is not None:
                edata[field_name] = serialize_item(eq_item)
        # Player-level full save
        edata.update(player_to_full_save_data(player))

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


class TestClassFeaturesSaveRestore:
    """class_features must survive to_full_save_data → parse_player round-trip."""

    def test_fighter_defense_style_survives_round_trip(self) -> None:
        """Fighter Defense fighting style must persist through save/load."""
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)

        # Verify original
        fighter_feat = player.get_feature(FighterFeatures)
        assert fighter_feat is not None
        assert fighter_feat.fighting_style == FightingStyle.DEFENSE

        # Save → load
        save_data = player_to_full_save_data(player)
        restored = parse_player(save_data, item_catalog=catalog)

        # Must survive
        restored_feat = restored.get_feature(FighterFeatures)
        assert restored_feat is not None, "FighterFeatures lost after save/restore"
        assert restored_feat.fighting_style == FightingStyle.DEFENSE

    def test_rogue_sneak_attack_survives_round_trip(self) -> None:
        """Rogue sneak attack dice count must persist through save/load."""
        catalog = _load_item_catalog()
        player = _create_rogue(catalog)

        rogue_feat = player.get_feature(RogueFeatures)
        assert rogue_feat is not None
        assert rogue_feat.sneak_attack_dice == 1

        save_data = player_to_full_save_data(player)
        restored = parse_player(save_data, item_catalog=catalog)

        restored_feat = restored.get_feature(RogueFeatures)
        assert restored_feat is not None, "RogueFeatures lost after save/restore"
        assert restored_feat.sneak_attack_dice == 1

    def test_paladin_features_survive_round_trip(self) -> None:
        """Paladin features (no fighting style at L1) must persist through save/load."""
        catalog = _load_item_catalog()
        player = _create_paladin(catalog)

        paladin_feat = player.get_feature(PaladinFeatures)
        assert paladin_feat is not None

        save_data = player_to_full_save_data(player)
        restored = parse_player(save_data, item_catalog=catalog)

        restored_feat = restored.get_feature(PaladinFeatures)
        assert restored_feat is not None, "PaladinFeatures lost after save/restore"
        assert restored_feat.fighting_style is None  # Paladin L1 has no style

    def test_fighter_defense_ac_survives_round_trip(self) -> None:
        """Fighter with Defense + Chain Mail + Shield must have AC 19 after save/load.

        Chain Mail (base 16) + Shield (+2) + Defense (+1) = 19.
        """
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)

        assert effective_ac(player) == 19, f"Original AC wrong: {effective_ac(player)}"

        save_data = player_to_full_save_data(player)
        restored = parse_player(save_data, item_catalog=catalog)

        assert effective_ac(restored) == 19, (
            f"AC dropped to {effective_ac(restored)} after save/restore — "
            f"Defense style lost? class_features: {restored.class_features}"
        )


def _create_player_with_ring(item_catalog: dict[str, ItemContent]) -> PlayerCharacter:
    """Create a fighter with ring_of_protection equipped."""
    parse_data: dict[str, Any] = {
        "name": "Ring Bearer",
        "race": "human",
        "class": "fighter",
        "level": 1,
        "alignment": "true_neutral",
        "hp": 12,
        "ac": 10,
        "gold": 0,
        "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
        "items": [
            {"ref": "ring_of_protection", "equipped": True},
        ],
    }
    return parse_player(parse_data, item_catalog=item_catalog)


class TestAccessoryModifierRoundTrip:
    """Accessory grant_modifiers must survive to_full_save_data → parse_player."""

    def test_ring_modifier_survives_save_restore(self) -> None:
        catalog = _load_item_catalog()
        player = _create_player_with_ring(catalog)

        assert player.equipped_ring is not None, "Ring not equipped"
        assert player.equipped_ring.accessory_def is not None
        assert len(player.equipped_ring.accessory_def.grant_modifiers) > 0, "Ring has no modifiers before save"

        ac_before = effective_ac(player)

        save_data = player_to_full_save_data(player)
        restored = parse_player(save_data, item_catalog=catalog)

        assert restored.equipped_ring is not None, "Ring lost after save/restore"
        assert restored.equipped_ring.accessory_def is not None
        assert len(restored.equipped_ring.accessory_def.grant_modifiers) > 0, (
            "Ring modifiers dropped after save/restore — grant_modifiers key not accepted by ItemContent"
        )
        assert effective_ac(restored) == ac_before, (
            f"AC changed after save/restore: {ac_before} → {effective_ac(restored)}"
        )

    def test_item_content_rejects_unknown_keys(self) -> None:
        """ItemContent with extra="forbid" must raise on unknown fields."""
        with pytest.raises(ValidationError):
            ItemContent.model_validate({"name": "Test", "type": "accessory", "unknown_field": "oops"})

    def test_all_catalog_items_validate(self) -> None:
        """All authored catalog items must still validate after extra="forbid"."""
        catalog_dir = Path(__file__).resolve().parents[2] / "content" / "catalogs" / "items"
        catalog = load_catalog(catalog_dir, ItemContent)
        assert len(catalog) > 0, "Catalog is empty"


class TestXPRoundTrip:
    """experience and level_up_available must survive to_full_save_data → parse_player."""

    def test_xp_survives_round_trip(self) -> None:
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)

        player.experience = 300
        player.level_up_available = True

        save_data = player_to_full_save_data(player)
        restored = parse_player(save_data, item_catalog=catalog)

        assert restored.experience == 300, f"XP lost: got {restored.experience}"
        assert restored.level_up_available is True, "level_up_available lost after save/restore"

    def test_zero_xp_survives_round_trip(self) -> None:
        catalog = _load_item_catalog()
        player = _create_fighter(catalog)

        player.experience = 0
        player.level_up_available = False

        save_data = player_to_full_save_data(player)
        restored = parse_player(save_data, item_catalog=catalog)

        assert restored.experience == 0
        assert restored.level_up_available is False
