"""Tests for item catalog loading and NPC/player item reference resolution.

Covers: item catalog loading from directory, ref-based item resolution with overrides,
inline fallback, unknown ref error, merchant inventory, player equipment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from dnd_simulator.content_loader.items import parse_items
from dnd_simulator.content_loader.schemas import ItemContent
from dnd_simulator.core.items import ItemType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(data, f)


def _dagger_data() -> dict[str, Any]:
    return {
        "name": "Dagger",
        "type": "weapon",
        "weapon_id": "dagger",
        "category": "simple",
        "attack_name": "dagger strike",
        "damage": [{"dice": "1d4", "type": "piercing"}],
        "ability": "dex",
        "is_finesse": True,
    }


def _health_potion_data() -> dict[str, Any]:
    return {
        "name": "Health Potion",
        "type": "potion",
        "heal_dice": "2d4+2",
    }


def _make_item_catalog() -> dict[str, ItemContent]:
    return {
        "dagger": ItemContent.model_validate(_dagger_data()),
        "health_potion": ItemContent.model_validate(_health_potion_data()),
    }


# ---------------------------------------------------------------------------
# 1. Item catalog loads all YAML files from directory
# ---------------------------------------------------------------------------


class TestItemCatalogLoading:
    def test_loads_item_catalog_files(self, tmp_path: Path) -> None:
        """Load item catalog from directory — each YAML file is one item."""
        from dnd_simulator.content_loader.catalogs import load_catalog

        catalog_dir = tmp_path / "items"
        catalog_dir.mkdir()
        _write_yaml(catalog_dir / "dagger.yaml", _dagger_data())
        _write_yaml(catalog_dir / "health_potion.yaml", _health_potion_data())

        result = load_catalog(catalog_dir, ItemContent)

        assert set(result.keys()) == {"dagger", "health_potion"}
        assert result["dagger"].name == "Dagger"
        assert result["dagger"].type == ItemType.WEAPON
        assert result["health_potion"].type == ItemType.POTION


# ---------------------------------------------------------------------------
# 2. NPC item reference — ref only
# ---------------------------------------------------------------------------


class TestItemReferenceResolution:
    def test_ref_only_resolves_to_catalog_item(self) -> None:
        """An item with 'ref: dagger' resolves to catalog dagger definition."""
        catalog = _make_item_catalog()
        items_data = [{"ref": "dagger"}]

        items = parse_items(items_data, item_catalog=catalog)

        assert len(items) == 1
        assert items[0].name == "Dagger"
        assert items[0].item_type == ItemType.WEAPON
        assert items[0].weapon_def is not None
        assert items[0].weapon_def.weapon_id == "dagger"

    # ---------------------------------------------------------------------------
    # 3. NPC item reference — ref + overrides
    # ---------------------------------------------------------------------------

    def test_ref_with_overrides(self) -> None:
        """An item with ref + overrides merges correctly."""
        catalog = _make_item_catalog()
        items_data = [{"ref": "dagger", "equipped": True, "price": 200}]

        items = parse_items(items_data, item_catalog=catalog)

        assert len(items) == 1
        assert items[0].name == "Dagger"
        assert items[0].price == 200
        assert items[0].params.get("equipped") is True

    # ---------------------------------------------------------------------------
    # 4. Inline item (no ref) still works
    # ---------------------------------------------------------------------------

    def test_inline_item_still_works(self) -> None:
        """An item without 'ref' parses as full inline definition."""
        catalog = _make_item_catalog()
        items_data = [_dagger_data()]

        items = parse_items(items_data, item_catalog=catalog)

        assert len(items) == 1
        assert items[0].name == "Dagger"
        assert items[0].weapon_def is not None

    # ---------------------------------------------------------------------------
    # 5. Unknown ref fails
    # ---------------------------------------------------------------------------

    def test_unknown_ref_raises(self) -> None:
        """An item with ref to nonexistent catalog entry raises RuntimeError."""
        catalog = _make_item_catalog()
        items_data = [{"ref": "vorpal_sword"}]

        with pytest.raises(RuntimeError, match="vorpal_sword"):
            parse_items(items_data, item_catalog=catalog)

    # ---------------------------------------------------------------------------
    # 6. Merchant inventory from catalog refs
    # ---------------------------------------------------------------------------

    def test_merchant_items_from_catalog(self) -> None:
        """Load NPC with merchant role and catalog-referenced items."""
        from dnd_simulator.content_loader.creatures import parse_npc

        catalog = _make_item_catalog()
        npc_data: dict[str, Any] = {
            "name": {"en": "Test Merchant"},
            "role": "merchant",
            "gold": 500,
            "start_location": "market",
            "items": [
                {"ref": "health_potion", "price": 50},
                {"ref": "dagger", "price": 200},
            ],
        }

        npc = parse_npc("merchant1", npc_data, lang="en", item_catalog=catalog)

        # Merchant has items in inventory (none equipped)
        all_items = list(npc.inventory)
        if npc.equipped_weapon:
            all_items.append(npc.equipped_weapon)
        assert len(all_items) == 2
        item_names = {i.name for i in all_items}
        assert "Health Potion" in item_names
        assert "Dagger" in item_names
        # Check prices resolved
        potion = next(i for i in all_items if i.name == "Health Potion")
        assert potion.price == 50

    # ---------------------------------------------------------------------------
    # 7. Player items from catalog refs
    # ---------------------------------------------------------------------------

    def test_player_items_from_catalog(self) -> None:
        """Player YAML with ref + equipped resolves correctly."""
        from dnd_simulator.content_loader.creatures import parse_player

        catalog = _make_item_catalog()
        player_data: dict[str, Any] = {
            "name": {"en": "Hero"},
            "race": "human",
            "class": "fighter",
            "start_location": "town",
            "items": [
                {"ref": "dagger", "equipped": True},
            ],
        }

        player = parse_player(player_data, lang="en", item_catalog=catalog)

        assert player.equipped_weapon is not None
        assert player.equipped_weapon.name == "Dagger"
        assert player.equipped_weapon.weapon_def is not None

    # ---------------------------------------------------------------------------
    # Mixed: ref and inline items together
    # ---------------------------------------------------------------------------

    def test_mixed_ref_and_inline(self) -> None:
        """Items list can contain both ref-based and inline items."""
        catalog = _make_item_catalog()
        items_data = [
            {"ref": "dagger"},
            {
                "name": "Custom Artifact",
                "type": "weapon",
                "weapon_id": "artifact",
                "attack_name": "artifact strike",
                "damage": [{"dice": "2d6", "type": "slashing"}],
            },
        ]

        items = parse_items(items_data, item_catalog=catalog)

        assert len(items) == 2
        assert items[0].name == "Dagger"
        assert items[1].name == "Custom Artifact"


# ---------------------------------------------------------------------------
# Weapon properties round-trip
# ---------------------------------------------------------------------------


class TestWeaponPropertiesRoundTrip:
    def test_two_handed_weapon_loads(self) -> None:
        """YAML with is_two_handed: true → WeaponDef(is_two_handed=True)."""
        items_data = [
            {
                "name": "Greatsword",
                "type": "weapon",
                "weapon_id": "greatsword",
                "attack_name": "greatsword slash",
                "category": "martial",
                "damage": [{"dice": "2d6", "type": "slashing"}],
                "is_two_handed": True,
                "is_heavy": True,
            },
        ]
        items = parse_items(items_data, item_catalog={})
        assert len(items) == 1
        wd = items[0].weapon_def
        assert wd is not None
        assert wd.is_two_handed is True
        assert wd.is_heavy is True
        assert wd.is_light is False

    def test_weapon_without_properties_defaults_false(self) -> None:
        """YAML without weapon properties → all default to False."""
        items_data = [
            {
                "name": "Longsword",
                "type": "weapon",
                "weapon_id": "longsword",
                "attack_name": "slash",
                "category": "martial",
                "damage": [{"dice": "1d8", "type": "slashing"}],
            },
        ]
        items = parse_items(items_data, item_catalog={})
        wd = items[0].weapon_def
        assert wd is not None
        assert wd.is_two_handed is False
        assert wd.is_light is False
        assert wd.is_heavy is False

    def test_light_finesse_weapon_loads(self) -> None:
        """YAML with is_light: true, is_finesse: true."""
        items_data = [
            {
                "name": "Shortsword",
                "type": "weapon",
                "weapon_id": "shortsword",
                "attack_name": "stab",
                "category": "martial",
                "damage": [{"dice": "1d6", "type": "piercing"}],
                "is_light": True,
                "is_finesse": True,
            },
        ]
        items = parse_items(items_data, item_catalog={})
        wd = items[0].weapon_def
        assert wd is not None
        assert wd.is_light is True
        assert wd.is_finesse is True
        assert wd.is_two_handed is False
