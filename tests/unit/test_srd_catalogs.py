"""Tests for SRD weapon and armor catalog integrity.

Validates that all catalog YAML files load correctly and have accurate D&D 5e stats.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.content_loader.catalogs import load_catalog
from dnd_simulator.content_loader.items import parse_items
from dnd_simulator.content_loader.schemas import ItemContent
from dnd_simulator.core.items import ArmorCategory, ItemType, WeaponCategory

CATALOG_DIR = Path(__file__).resolve().parents[2] / "content" / "catalogs" / "items"


@pytest.fixture()
def catalog() -> dict[str, ItemContent]:
    return load_catalog(CATALOG_DIR, ItemContent)


# ---------------------------------------------------------------------------
# All catalog files load without errors
# ---------------------------------------------------------------------------


class TestCatalogIntegrity:
    def test_all_weapon_files_load(self, catalog: dict[str, ItemContent]) -> None:
        """Every weapon catalog entry loads and validates."""
        weapons = {k: v for k, v in catalog.items() if v.type == ItemType.WEAPON}
        assert len(weapons) >= 12

    def test_all_armor_files_load(self, catalog: dict[str, ItemContent]) -> None:
        """Every armor catalog entry loads and validates."""
        armors = {k: v for k, v in catalog.items() if v.type == ItemType.ARMOR}
        assert len(armors) >= 12

    def test_all_shield_files_load(self, catalog: dict[str, ItemContent]) -> None:
        """Shield catalog entry loads and validates."""
        shields = {k: v for k, v in catalog.items() if v.type == ItemType.SHIELD}
        assert len(shields) >= 1

    def test_all_catalog_items_parse_to_runtime(self, catalog: dict[str, ItemContent]) -> None:
        """Every catalog entry converts to a runtime Item without errors."""
        for stem, content in catalog.items():
            items = parse_items([content.model_dump(exclude_none=True)], item_catalog={})
            assert len(items) == 1, f"Failed to parse catalog entry '{stem}'"


# ---------------------------------------------------------------------------
# Specific weapon stats
# ---------------------------------------------------------------------------


class TestWeaponStats:
    def test_greatsword(self, catalog: dict[str, ItemContent]) -> None:
        entry = catalog["greatsword"]
        assert entry.type == ItemType.WEAPON
        assert entry.category == "martial"
        assert entry.is_two_handed is True
        assert entry.is_heavy is True
        assert len(entry.damage or []) == 1
        assert entry.damage[0].dice == "2d6"  # type: ignore[index]
        assert entry.damage[0].type.value == "slashing"  # type: ignore[index]

    def test_rapier(self, catalog: dict[str, ItemContent]) -> None:
        entry = catalog["rapier"]
        assert entry.type == ItemType.WEAPON
        assert entry.category == "martial"
        assert entry.is_finesse is True
        assert entry.is_two_handed is not True
        assert len(entry.damage or []) == 1
        assert entry.damage[0].dice == "1d8"  # type: ignore[index]
        assert entry.damage[0].type.value == "piercing"  # type: ignore[index]

    def test_shortsword(self, catalog: dict[str, ItemContent]) -> None:
        entry = catalog["shortsword"]
        assert entry.type == ItemType.WEAPON
        assert entry.category == "martial"
        assert entry.is_finesse is True
        assert entry.is_light is True
        assert len(entry.damage or []) == 1
        assert entry.damage[0].dice == "1d6"  # type: ignore[index]
        assert entry.damage[0].type.value == "piercing"  # type: ignore[index]

    def test_dagger(self, catalog: dict[str, ItemContent]) -> None:
        entry = catalog["dagger"]
        assert entry.type == ItemType.WEAPON
        assert entry.category == "simple"
        assert entry.is_finesse is True
        assert entry.is_light is True
        assert len(entry.damage or []) == 1
        assert entry.damage[0].dice == "1d4"  # type: ignore[index]
        assert entry.damage[0].type.value == "piercing"  # type: ignore[index]

    def test_longbow(self, catalog: dict[str, ItemContent]) -> None:
        entry = catalog["longbow"]
        assert entry.type == ItemType.WEAPON
        assert entry.ability == "dex"
        assert entry.is_two_handed is True
        assert entry.is_heavy is True
        assert len(entry.damage or []) == 1
        assert entry.damage[0].dice == "1d8"  # type: ignore[index]
        assert entry.damage[0].type.value == "piercing"  # type: ignore[index]


# ---------------------------------------------------------------------------
# Specific armor stats
# ---------------------------------------------------------------------------


class TestArmorStats:
    def test_plate(self, catalog: dict[str, ItemContent]) -> None:
        entry = catalog["plate"]
        assert entry.type == ItemType.ARMOR
        assert entry.category == "heavy"
        assert entry.base_ac == 18
        assert entry.max_dex_bonus == 0

    def test_leather(self, catalog: dict[str, ItemContent]) -> None:
        entry = catalog["leather"]
        assert entry.type == ItemType.ARMOR
        assert entry.category == "light"
        assert entry.base_ac == 11
        # Light armor: max_dex_bonus not set in YAML → derived as 99 by converter

    def test_chain_mail(self, catalog: dict[str, ItemContent]) -> None:
        entry = catalog["chain_mail"]
        assert entry.type == ItemType.ARMOR
        assert entry.category == "heavy"
        assert entry.base_ac == 16
        assert entry.max_dex_bonus == 0

    def test_shield(self, catalog: dict[str, ItemContent]) -> None:
        entry = catalog["shield"]
        assert entry.type == ItemType.SHIELD
        assert entry.ac_bonus == 2


# ---------------------------------------------------------------------------
# Cross-check: D&D rules constraints
# ---------------------------------------------------------------------------


class TestWeaponRulesConstraints:
    def test_no_finesse_two_handed(self, catalog: dict[str, ItemContent]) -> None:
        """No SRD weapon has both is_finesse and is_two_handed."""
        weapons = {k: v for k, v in catalog.items() if v.type == ItemType.WEAPON}
        for name, w in weapons.items():
            assert not (w.is_finesse and w.is_two_handed), f"{name} has both finesse and two-handed"

    def test_martial_two_handed_are_heavy(self, catalog: dict[str, ItemContent]) -> None:
        """All martial two-handed weapons are also heavy (greatsword, greataxe, longbow)."""
        weapons = {k: v for k, v in catalog.items() if v.type == ItemType.WEAPON}
        for name, w in weapons.items():
            if w.category == "martial" and w.is_two_handed:
                assert w.is_heavy, f"{name} is martial + two-handed but not heavy"

    def test_light_weapons_are_one_handed(self, catalog: dict[str, ItemContent]) -> None:
        """All light weapons are one-handed."""
        weapons = {k: v for k, v in catalog.items() if v.type == ItemType.WEAPON}
        for name, w in weapons.items():
            if w.is_light:
                assert not w.is_two_handed, f"{name} is light but two-handed"


# ---------------------------------------------------------------------------
# Runtime conversion: catalog → WeaponDef / ArmorDef / ShieldDef
# ---------------------------------------------------------------------------


class TestCatalogRuntimeConversion:
    def test_greatsword_weapon_def(self, catalog: dict[str, ItemContent]) -> None:
        items = parse_items([{"ref": "greatsword"}], item_catalog=catalog)
        wd = items[0].weapon_def
        assert wd is not None
        assert wd.weapon_id == "greatsword"
        assert wd.category == WeaponCategory.MARTIAL
        assert wd.is_two_handed is True
        assert wd.is_heavy is True
        assert len(wd.damage) == 1
        assert wd.damage[0].dice == "2d6"

    def test_plate_armor_def(self, catalog: dict[str, ItemContent]) -> None:
        items = parse_items([{"ref": "plate"}], item_catalog=catalog)
        ad = items[0].armor_def
        assert ad is not None
        assert ad.armor_id == "plate"
        assert ad.category == ArmorCategory.HEAVY
        assert ad.base_ac == 18
        assert ad.max_dex_bonus == 0

    def test_leather_armor_def(self, catalog: dict[str, ItemContent]) -> None:
        items = parse_items([{"ref": "leather"}], item_catalog=catalog)
        ad = items[0].armor_def
        assert ad is not None
        assert ad.category == ArmorCategory.LIGHT
        assert ad.base_ac == 11
        assert ad.max_dex_bonus == 99

    def test_shield_def(self, catalog: dict[str, ItemContent]) -> None:
        items = parse_items([{"ref": "shield"}], item_catalog=catalog)
        sd = items[0].shield_def
        assert sd is not None
        assert sd.ac_bonus == 2
