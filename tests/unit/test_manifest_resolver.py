"""Tests for manifest resolution and standalone settlements loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dnd_simulator.content_loader.manifest import load_world_meta_from_manifest, resolve_manifest
from dnd_simulator.content_loader.world import load_settlements
from dnd_simulator.layers.settlements.models import SettlementType

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
WORLDS_DIR = CONTENT_DIR / "worlds"
LIBRARY_DIR = CONTENT_DIR / "library"

LAYER_TYPES = {"geography", "politics", "settlements", "ecology", "entities"}


class TestManifestResolutionLibrary:
    """sword_vale: all layers source=library."""

    def test_resolves_all_five_layers(self) -> None:
        result = resolve_manifest(WORLDS_DIR / "sword_vale", CONTENT_DIR)
        assert set(result.keys()) == LAYER_TYPES

    def test_library_paths_point_into_library_dir(self) -> None:
        result = resolve_manifest(WORLDS_DIR / "sword_vale", CONTENT_DIR)
        for layer_type, path in result.items():
            expected = LIBRARY_DIR / layer_type / "sword_vale"
            assert path == expected, f"{layer_type}: expected {expected}, got {path}"

    def test_all_resolved_paths_exist(self) -> None:
        result = resolve_manifest(WORLDS_DIR / "sword_vale", CONTENT_DIR)
        for layer_type, path in result.items():
            assert path.is_dir(), f"{layer_type}: resolved path {path} does not exist"


class TestManifestResolutionCustom:
    """test_vale: all layers source=custom."""

    def test_resolves_all_five_layers(self) -> None:
        result = resolve_manifest(WORLDS_DIR / "test_vale", CONTENT_DIR)
        assert set(result.keys()) == LAYER_TYPES

    def test_custom_paths_point_into_world_dir(self) -> None:
        result = resolve_manifest(WORLDS_DIR / "test_vale", CONTENT_DIR)
        for layer_type, path in result.items():
            expected = WORLDS_DIR / "test_vale" / layer_type
            assert path == expected, f"{layer_type}: expected {expected}, got {path}"

    def test_all_resolved_paths_exist(self) -> None:
        result = resolve_manifest(WORLDS_DIR / "test_vale", CONTENT_DIR)
        for layer_type, path in result.items():
            assert path.is_dir(), f"{layer_type}: resolved path {path} does not exist"


class TestManifestResolutionErrors:
    def test_missing_template_raises(self, tmp_path: Path) -> None:
        world_dir = tmp_path / "bad_world"
        world_dir.mkdir()
        manifest = {
            "name": {"en": "Bad"},
            "description": {"en": "Bad world"},
            "layers": {
                "geography": {"source": "library", "template": "nonexistent", "version": "1.0"},
                "politics": {"source": "custom"},
                "settlements": {"source": "custom"},
                "ecology": {"source": "custom"},
                "entities": {"source": "custom"},
            },
        }
        # Create custom dirs so only the library ref fails
        for lt in ["politics", "settlements", "ecology", "entities"]:
            (world_dir / lt).mkdir()

        with open(world_dir / "manifest.yaml", "w") as f:
            yaml.dump(manifest, f)

        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "library").mkdir()

        with pytest.raises(RuntimeError, match="nonexistent"):
            resolve_manifest(world_dir, content_dir)

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        world_dir = tmp_path / "no_manifest"
        world_dir.mkdir()

        with pytest.raises(RuntimeError, match=r"manifest\.yaml"):
            resolve_manifest(world_dir, tmp_path)


class TestLoadWorldMetaFromManifest:
    def test_reads_sword_vale_metadata(self) -> None:
        meta = load_world_meta_from_manifest(WORLDS_DIR / "sword_vale")
        assert meta["name"] == "Sword Vale"
        assert "Silverport" in meta["description"]
        assert meta["default_player_faction"] == "kingdom"

    def test_reads_test_vale_metadata(self) -> None:
        meta = load_world_meta_from_manifest(WORLDS_DIR / "test_vale")
        assert meta["name"] == "Test Vale"
        assert meta["default_player_faction"] == "militia"


class TestStandaloneSettlementsLoading:
    """load_settlements reads standalone settlements.yaml with per-settlement region field."""

    def test_loads_library_settlements(self) -> None:
        # Library settlements dir has standalone format
        path = LIBRARY_DIR / "settlements" / "sword_vale"
        settlements = load_settlements(path)
        assert len(settlements) == 10
        city = next(s for s in settlements if s.id == "silverport_city")
        assert city.population == 5000
        assert city.type == SettlementType.CITY
        assert city.region_id == "silverport"

    def test_loads_custom_settlements(self) -> None:
        path = WORLDS_DIR / "test_vale" / "settlements"
        settlements = load_settlements(path)
        assert len(settlements) == 1
        town = settlements[0]
        assert town.id == "crossroads_town"
        assert town.region_id == "crossroads"
        assert town.type == SettlementType.TOWN

    def test_missing_region_field_raises(self, tmp_path: Path) -> None:
        bad_data = {
            "orphan_village": {
                "name": {"en": "Orphan"},
                "type": "village",
                "population": 50,
            }
        }
        with open(tmp_path / "settlements.yaml", "w") as f:
            yaml.dump(bad_data, f)

        with pytest.raises(KeyError):
            load_settlements(tmp_path)
