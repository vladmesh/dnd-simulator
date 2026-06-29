"""Tests for content/library/ template structure.

Validates that the library directory layout, metadata files,
and extracted settlements match the canonical format.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
LIBRARY_DIR = CONTENT_DIR / "library"

# Expected data files per layer type (besides metadata.yaml which is universal)
EXPECTED_DATA_FILES: dict[str, list[str]] = {
    "geography": ["regions.yaml", "locations.yaml"],
    "politics": ["nations.yaml", "factions.yaml"],
    "settlements": ["settlements.yaml"],
    "ecology": ["monsters.yaml", "squads.yaml"],
    "entities": ["npcs.yaml"],
}

METADATA_REQUIRED_FIELDS = {"name", "layer_type", "version"}

# Hardcoded counts from sword_vale original data
SWORD_VALE_COUNTS = {
    "regions": 7,
    "locations": 34,
    "nations": 3,
    "factions": 5,
    "npcs": 7,
    "settlements": 10,
    "squads": 3,
    "monster_templates": 8,
    "encounters": 9,
}


class TestLibraryTemplateCompleteness:
    """Every template dir has valid metadata and expected data files."""

    def test_library_has_all_layer_types(self) -> None:
        layer_types = {p.name for p in LIBRARY_DIR.iterdir() if p.is_dir()}
        assert layer_types == set(EXPECTED_DATA_FILES.keys())

    def test_sword_vale_template_exists_for_each_layer(self) -> None:
        for layer_type in EXPECTED_DATA_FILES:
            template_dir = LIBRARY_DIR / layer_type / "sword_vale"
            assert template_dir.is_dir(), f"Missing template: {template_dir}"

    def test_metadata_exists_and_valid(self) -> None:
        for layer_type in EXPECTED_DATA_FILES:
            meta_path = LIBRARY_DIR / layer_type / "sword_vale" / "metadata.yaml"
            assert meta_path.exists(), f"Missing metadata: {meta_path}"
            with open(meta_path) as f:
                meta = yaml.safe_load(f)
            missing = METADATA_REQUIRED_FIELDS - set(meta.keys())
            assert not missing, f"{meta_path}: missing fields {missing}"

    def test_metadata_layer_type_matches_directory(self) -> None:
        for layer_type in EXPECTED_DATA_FILES:
            meta_path = LIBRARY_DIR / layer_type / "sword_vale" / "metadata.yaml"
            with open(meta_path) as f:
                meta = yaml.safe_load(f)
            assert meta["layer_type"] == layer_type, (
                f"{meta_path}: layer_type={meta['layer_type']!r} but dir is {layer_type!r}"
            )

    def test_expected_data_files_exist(self) -> None:
        for layer_type, files in EXPECTED_DATA_FILES.items():
            template_dir = LIBRARY_DIR / layer_type / "sword_vale"
            for filename in files:
                filepath = template_dir / filename
                assert filepath.exists(), f"Missing data file: {filepath}"


class TestSettlementsExtraction:
    """Settlements extracted from regions.yaml into standalone settlements.yaml."""

    def _load_settlements(self) -> dict[str, object]:
        path = LIBRARY_DIR / "settlements" / "sword_vale" / "settlements.yaml"
        with open(path) as f:
            return yaml.safe_load(f)  # type: ignore[no-any-return]

    def _load_regions(self) -> dict[str, object]:
        path = LIBRARY_DIR / "geography" / "sword_vale" / "regions.yaml"
        with open(path) as f:
            return yaml.safe_load(f)  # type: ignore[no-any-return]

    def test_every_settlement_has_region_field(self) -> None:
        settlements = self._load_settlements()
        for sid, sdata in settlements.items():
            assert "region" in sdata, f"Settlement {sid!r} missing 'region' field"  # type: ignore[operator]

    def test_settlement_regions_exist_in_regions_yaml(self) -> None:
        settlements = self._load_settlements()
        regions = self._load_regions()
        region_ids = set(regions.keys())
        for sid, sdata in settlements.items():
            assert sdata["region"] in region_ids, (  # type: ignore[index]
                f"Settlement {sid!r} references region {sdata['region']!r} "  # type: ignore[index]
                f"which is not in regions.yaml"
            )

    def test_regions_yaml_has_no_settlements_key(self) -> None:
        regions = self._load_regions()
        for rid, rdata in regions.items():
            assert "settlements" not in rdata, (  # type: ignore[operator]
                f"Region {rid!r} still has 'settlements' key in library regions.yaml"
            )


class TestDataPreservation:
    """Counts in library match original sword_vale data."""

    def test_region_count(self) -> None:
        with open(LIBRARY_DIR / "geography" / "sword_vale" / "regions.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data) == SWORD_VALE_COUNTS["regions"]

    def test_location_count(self) -> None:
        with open(LIBRARY_DIR / "geography" / "sword_vale" / "locations.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data) == SWORD_VALE_COUNTS["locations"]

    def test_nation_count(self) -> None:
        with open(LIBRARY_DIR / "politics" / "sword_vale" / "nations.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data) == SWORD_VALE_COUNTS["nations"]

    def test_faction_count(self) -> None:
        with open(LIBRARY_DIR / "politics" / "sword_vale" / "factions.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data) == SWORD_VALE_COUNTS["factions"]

    def test_npc_count(self) -> None:
        with open(LIBRARY_DIR / "entities" / "sword_vale" / "npcs.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data) == SWORD_VALE_COUNTS["npcs"]

    def test_settlement_count(self) -> None:
        with open(LIBRARY_DIR / "settlements" / "sword_vale" / "settlements.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data) == SWORD_VALE_COUNTS["settlements"]

    def test_squad_count(self) -> None:
        with open(LIBRARY_DIR / "ecology" / "sword_vale" / "squads.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data) == SWORD_VALE_COUNTS["squads"]

    def test_monster_template_count(self) -> None:
        with open(LIBRARY_DIR / "ecology" / "sword_vale" / "monsters.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data["templates"]) == SWORD_VALE_COUNTS["monster_templates"]

    def test_encounter_count(self) -> None:
        with open(LIBRARY_DIR / "ecology" / "sword_vale" / "monsters.yaml") as f:
            data = yaml.safe_load(f)
        assert len(data["encounters"]) == SWORD_VALE_COUNTS["encounters"]
