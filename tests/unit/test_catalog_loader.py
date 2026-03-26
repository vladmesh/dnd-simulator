"""Tests for catalog loader and monster catalog references.

Covers: generic catalog loading from directory, monster base reference resolution
with overrides, inline fallback, error cases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from dnd_simulator.content_loader.schemas import MonsterTemplateContent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(data, f)


def _goblin_data() -> dict[str, Any]:
    return {
        "name": {"en": "Goblin", "ru": "Гоблин"},
        "hp": 7,
        "ac": 15,
        "speed": 30,
        "cr": 0.25,
        "ability_scores": {"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
        "attacks": [
            {"name": "scimitar", "ability": "dex", "damage": [{"dice": "1d6", "type": "slashing"}], "reach": 5}
        ],
        "faction": "goblin_tribe",
    }


def _wolf_data() -> dict[str, Any]:
    return {
        "name": {"en": "Wolf", "ru": "Волк"},
        "hp": 11,
        "ac": 13,
        "speed": 40,
        "cr": 0.25,
        "ability_scores": {"str": 12, "dex": 15, "con": 12, "int": 3, "wis": 12, "cha": 6},
        "attacks": [{"name": "bite", "ability": "dex", "damage": [{"dice": "2d4", "type": "piercing"}], "reach": 5}],
        "faction": "wildlife",
    }


# ---------------------------------------------------------------------------
# 1. Catalog loader — loads all YAML files, indexes by filename stem
# ---------------------------------------------------------------------------


class TestCatalogLoader:
    def test_loads_all_yaml_files_indexed_by_stem(self, tmp_path: Path) -> None:
        catalog_dir = tmp_path / "monsters"
        catalog_dir.mkdir()
        _write_yaml(catalog_dir / "goblin.yaml", _goblin_data())
        _write_yaml(catalog_dir / "wolf.yaml", _wolf_data())

        from dnd_simulator.content_loader.catalogs import load_catalog

        result = load_catalog(catalog_dir, MonsterTemplateContent)

        assert set(result.keys()) == {"goblin", "wolf"}
        assert result["goblin"].hp == 7
        assert result["wolf"].speed == 40

    def test_fails_on_invalid_yaml(self, tmp_path: Path) -> None:
        catalog_dir = tmp_path / "monsters"
        catalog_dir.mkdir()
        # Missing required fields (name, hp, ac, speed, cr)
        _write_yaml(catalog_dir / "bad.yaml", {"name": "Bad"})

        from dnd_simulator.content_loader.catalogs import load_catalog

        with pytest.raises(RuntimeError, match=r"bad\.yaml"):
            load_catalog(catalog_dir, MonsterTemplateContent)

    def test_empty_directory_returns_empty_dict(self, tmp_path: Path) -> None:
        catalog_dir = tmp_path / "monsters"
        catalog_dir.mkdir()

        from dnd_simulator.content_loader.catalogs import load_catalog

        assert load_catalog(catalog_dir, MonsterTemplateContent) == {}

    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        from dnd_simulator.content_loader.catalogs import load_catalog

        with pytest.raises(RuntimeError, match="does not exist"):
            load_catalog(tmp_path / "nonexistent", MonsterTemplateContent)


# ---------------------------------------------------------------------------
# 2. Monster reference resolution
# ---------------------------------------------------------------------------


class TestMonsterReferenceResolution:
    """Test that world monster templates can reference catalog entries via 'base'."""

    def _make_catalog(self) -> dict[str, MonsterTemplateContent]:
        return {
            "goblin": MonsterTemplateContent.model_validate(_goblin_data()),
            "wolf": MonsterTemplateContent.model_validate(_wolf_data()),
        }

    def test_base_only_produces_identical_template(self) -> None:
        from dnd_simulator.content_loader.monsters import resolve_monster_template

        catalog = self._make_catalog()
        data: dict[str, Any] = {"base": "goblin"}

        result = resolve_monster_template("g1", data, catalog, lang="en")

        assert result.name == "Goblin"
        assert result.hp == 7
        assert result.ac == 15
        assert result.faction_id == "goblin_tribe"

    def test_base_with_overrides(self) -> None:
        from dnd_simulator.content_loader.monsters import resolve_monster_template

        catalog = self._make_catalog()
        data: dict[str, Any] = {"base": "goblin", "hp": 20, "faction": "dark_goblin"}

        result = resolve_monster_template("g2", data, catalog, lang="en")

        assert result.hp == 20
        assert result.faction_id == "dark_goblin"
        # Non-overridden fields come from catalog
        assert result.ac == 15
        assert result.name == "Goblin"

    def test_inline_without_base_still_works(self) -> None:
        from dnd_simulator.content_loader.monsters import resolve_monster_template

        catalog = self._make_catalog()
        data = _goblin_data()  # Full inline, no 'base' key

        result = resolve_monster_template("g3", data, catalog, lang="en")

        assert result.name == "Goblin"
        assert result.hp == 7

    def test_unknown_base_raises(self) -> None:
        from dnd_simulator.content_loader.monsters import resolve_monster_template

        catalog = self._make_catalog()
        data: dict[str, Any] = {"base": "dragon"}

        with pytest.raises(RuntimeError, match="dragon"):
            resolve_monster_template("g4", data, catalog, lang="en")

    def test_roundtrip_catalog_to_world_template(self, tmp_path: Path) -> None:
        """Load goblin from catalog file, reference in world with override, verify result."""
        from dnd_simulator.content_loader.catalogs import load_catalog
        from dnd_simulator.content_loader.monsters import resolve_monster_template

        catalog_dir = tmp_path / "monsters"
        catalog_dir.mkdir()
        _write_yaml(catalog_dir / "goblin.yaml", _goblin_data())

        catalog = load_catalog(catalog_dir, MonsterTemplateContent)
        data: dict[str, Any] = {"base": "goblin", "faction": "cave_goblins"}

        result = resolve_monster_template("g5", data, catalog, lang="en")

        assert result.hp == 7
        assert result.ac == 15
        assert result.faction_id == "cave_goblins"
        assert result.name == "Goblin"
        assert len(result.attacks) == 1
