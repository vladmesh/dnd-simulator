"""Tests for world manifest format and structure.

Validates manifest.yaml files, library references, test_vale completeness,
and absence of old-format worlds.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
WORLDS_DIR = CONTENT_DIR / "worlds"
LIBRARY_DIR = CONTENT_DIR / "library"

LAYER_TYPES = {"geography", "politics", "settlements", "ecology", "entities"}

# Expected data files per layer type for custom worlds
CUSTOM_DATA_FILES: dict[str, list[str]] = {
    "geography": ["regions.yaml", "locations.yaml"],
    "politics": ["nations.yaml"],
    "settlements": ["settlements.yaml"],
    "ecology": ["monsters.yaml", "squads.yaml"],
    "entities": ["npcs.yaml"],
}


class TestManifestValidity:
    """Every world dir has a valid manifest.yaml."""

    def test_all_worlds_have_manifest(self) -> None:
        for world_dir in sorted(WORLDS_DIR.iterdir()):
            if not world_dir.is_dir():
                continue
            manifest = world_dir / "manifest.yaml"
            assert manifest.exists(), f"World {world_dir.name} missing manifest.yaml"

    def test_manifest_has_required_fields(self) -> None:
        for world_dir in sorted(WORLDS_DIR.iterdir()):
            if not world_dir.is_dir():
                continue
            with open(world_dir / "manifest.yaml") as f:
                manifest = yaml.safe_load(f)
            assert "name" in manifest, f"{world_dir.name}: missing 'name'"
            assert "layers" in manifest, f"{world_dir.name}: missing 'layers'"

    def test_manifest_has_all_layer_types(self) -> None:
        for world_dir in sorted(WORLDS_DIR.iterdir()):
            if not world_dir.is_dir():
                continue
            with open(world_dir / "manifest.yaml") as f:
                manifest = yaml.safe_load(f)
            layer_types = set(manifest["layers"].keys())
            assert layer_types == LAYER_TYPES, f"{world_dir.name}: layers={layer_types}, expected={LAYER_TYPES}"

    def test_every_layer_has_source(self) -> None:
        for world_dir in sorted(WORLDS_DIR.iterdir()):
            if not world_dir.is_dir():
                continue
            with open(world_dir / "manifest.yaml") as f:
                manifest = yaml.safe_load(f)
            for layer_type, layer_def in manifest["layers"].items():
                assert "source" in layer_def, f"{world_dir.name}/{layer_type}: missing 'source'"

    def test_library_refs_have_template_and_version(self) -> None:
        for world_dir in sorted(WORLDS_DIR.iterdir()):
            if not world_dir.is_dir():
                continue
            with open(world_dir / "manifest.yaml") as f:
                manifest = yaml.safe_load(f)
            for layer_type, layer_def in manifest["layers"].items():
                if layer_def["source"] == "library":
                    assert "template" in layer_def, f"{world_dir.name}/{layer_type}: library source missing 'template'"
                    assert "version" in layer_def, f"{world_dir.name}/{layer_type}: library source missing 'version'"

    def test_custom_layers_have_data_subdirectory(self) -> None:
        for world_dir in sorted(WORLDS_DIR.iterdir()):
            if not world_dir.is_dir():
                continue
            with open(world_dir / "manifest.yaml") as f:
                manifest = yaml.safe_load(f)
            for layer_type, layer_def in manifest["layers"].items():
                if layer_def["source"] == "custom":
                    data_dir = world_dir / layer_type
                    assert data_dir.is_dir(), f"{world_dir.name}/{layer_type}: custom source but no data dir"
                    for filename in CUSTOM_DATA_FILES[layer_type]:
                        filepath = data_dir / filename
                        assert filepath.exists(), f"{world_dir.name}/{layer_type}: missing {filename}"


class TestLibraryReferenceResolution:
    """Library references in manifests resolve to existing templates."""

    def test_referenced_templates_exist(self) -> None:
        for world_dir in sorted(WORLDS_DIR.iterdir()):
            if not world_dir.is_dir():
                continue
            with open(world_dir / "manifest.yaml") as f:
                manifest = yaml.safe_load(f)
            for layer_type, layer_def in manifest["layers"].items():
                if layer_def["source"] == "library":
                    template = layer_def["template"]
                    template_dir = LIBRARY_DIR / layer_type / template
                    assert template_dir.is_dir(), (
                        f"{world_dir.name}/{layer_type}: template {template!r} not found at {template_dir}"
                    )

    def test_referenced_versions_match_metadata(self) -> None:
        for world_dir in sorted(WORLDS_DIR.iterdir()):
            if not world_dir.is_dir():
                continue
            with open(world_dir / "manifest.yaml") as f:
                manifest = yaml.safe_load(f)
            for layer_type, layer_def in manifest["layers"].items():
                if layer_def["source"] == "library":
                    template = layer_def["template"]
                    meta_path = LIBRARY_DIR / layer_type / template / "metadata.yaml"
                    with open(meta_path) as mf:
                        meta = yaml.safe_load(mf)
                    assert layer_def["version"] == meta["version"], (
                        f"{world_dir.name}/{layer_type}: version {layer_def['version']!r} "
                        f"!= metadata version {meta['version']!r}"
                    )


class TestTestValeCompleteness:
    """test_vale is a complete all-custom world with all layers populated."""

    test_vale = WORLDS_DIR / "test_vale"

    def _load(self, *path_parts: str) -> object:
        with open(self.test_vale.joinpath(*path_parts)) as f:
            return yaml.safe_load(f)

    def test_regions_have_connections(self) -> None:
        regions = self._load("geography", "regions.yaml")
        assert isinstance(regions, dict)
        for rid, rdata in regions.items():
            assert "connections" in rdata, f"Region {rid!r} has no connections"  # type: ignore[operator]
            assert len(rdata["connections"]) > 0, f"Region {rid!r} has empty connections"  # type: ignore[index]

    def test_locations_have_neighbors(self) -> None:
        locations = self._load("geography", "locations.yaml")
        assert isinstance(locations, dict)
        for lid, ldata in locations.items():
            assert "neighbors" in ldata, f"Location {lid!r} has no neighbors"  # type: ignore[operator]
            assert len(ldata["neighbors"]) > 0, f"Location {lid!r} has empty neighbors"  # type: ignore[index]

    def test_npcs_reference_valid_locations(self) -> None:
        locations = self._load("geography", "locations.yaml")
        assert isinstance(locations, dict)
        location_ids = set(locations.keys())
        npcs = self._load("entities", "npcs.yaml")
        assert isinstance(npcs, dict)
        for nid, ndata in npcs.items():
            assert ndata["start_location"] in location_ids, (  # type: ignore[index]
                f"NPC {nid!r} references location {ndata['start_location']!r} not in locations.yaml"  # type: ignore[index]
            )

    def test_squad_references_valid_monster_template(self) -> None:
        monsters = self._load("ecology", "monsters.yaml")
        assert isinstance(monsters, dict)
        template_ids = set(monsters["templates"].keys())
        squads = self._load("ecology", "squads.yaml")
        assert isinstance(squads, dict)
        for sid, sdata in squads.items():
            for member in sdata["members"]:  # type: ignore[index]
                assert member in template_ids, f"Squad {sid!r} member {member!r} not in monster templates"

    def test_squad_route_references_valid_locations(self) -> None:
        locations = self._load("geography", "locations.yaml")
        assert isinstance(locations, dict)
        location_ids = set(locations.keys())
        squads = self._load("ecology", "squads.yaml")
        assert isinstance(squads, dict)
        for sid, sdata in squads.items():
            route_or_territory = sdata.get("route") or sdata.get("territory", [])  # type: ignore[union-attr]
            for loc in route_or_territory:
                assert loc in location_ids, f"Squad {sid!r} references location {loc!r} not in locations.yaml"

    def test_settlements_reference_valid_regions(self) -> None:
        regions = self._load("geography", "regions.yaml")
        assert isinstance(regions, dict)
        region_ids = set(regions.keys())
        settlements = self._load("settlements", "settlements.yaml")
        assert isinstance(settlements, dict)
        for sid, sdata in settlements.items():
            assert sdata["region"] in region_ids, (  # type: ignore[index]
                f"Settlement {sid!r} references region {sdata['region']!r} not in regions.yaml"  # type: ignore[index]
            )


class TestNoOldFormatWorlds:
    """No world uses the old flat format (world.yaml without manifest.yaml)."""

    def test_no_world_yaml_only_worlds(self) -> None:
        """Every world dir that has world.yaml must also have manifest.yaml."""
        for world_dir in sorted(WORLDS_DIR.iterdir()):
            if not world_dir.is_dir():
                continue
            if (world_dir / "world.yaml").exists():
                assert (world_dir / "manifest.yaml").exists(), (
                    f"{world_dir.name}: has world.yaml but no manifest.yaml (old format)"
                )

    def test_deleted_worlds_are_gone(self) -> None:
        existing = {p.name for p in WORLDS_DIR.iterdir() if p.is_dir()}
        for old_world in ("arena", "village", "sneak_test"):
            assert old_world not in existing, f"Old world {old_world!r} still exists"
