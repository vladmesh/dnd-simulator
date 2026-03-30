"""Tests for directory-based world loading via manifest resolution.

Tests parser logic with in-memory fixtures — not tied to real content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.content_loader import (
    load_catalog,
    load_nations,
    load_npcs,
    load_settlements,
    load_world,
    load_world_meta_from_manifest,
    resolve_manifest,
)
from dnd_simulator.content_loader.schemas import ItemContent
from dnd_simulator.core.character import NpcRole

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
SWORD_VALE = CONTENT_DIR / "worlds" / "sword_vale"


class TestManifestResolution:
    """Verify that manifest resolution produces valid layer paths."""

    def test_resolve_manifest_returns_all_layers(self) -> None:
        layer_paths = resolve_manifest(SWORD_VALE, CONTENT_DIR)
        expected_layers = {"geography", "politics", "settlements", "ecology", "entities"}
        assert expected_layers.issubset(layer_paths.keys())
        for layer_type, path in layer_paths.items():
            assert path.exists(), f"Layer path for '{layer_type}' does not exist: {path}"

    def test_load_world_meta(self) -> None:
        meta = load_world_meta_from_manifest(SWORD_VALE)
        assert "name" in meta
        assert "description" in meta
        assert isinstance(meta["name"], str)
        assert len(meta["name"]) > 0


class TestParsersProduceValidObjects:
    """Verify parsers load real content without errors and return correct types.

    Assertions check structure (types, non-emptiness) — not specific content values,
    so these tests don't break when content is edited.
    """

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.layer_paths = resolve_manifest(SWORD_VALE, CONTENT_DIR)
        catalog_dir = CONTENT_DIR / "catalogs" / "items"
        self.item_catalog = load_catalog(catalog_dir, ItemContent) if catalog_dir.exists() else {}

    def test_load_regions(self) -> None:
        regions = load_world(self.layer_paths["geography"])
        assert len(regions) > 0
        for r in regions:
            assert r.id
            assert r.name

    def test_load_nations(self) -> None:
        nations = load_nations(self.layer_paths["politics"])
        assert len(nations) > 0
        for n in nations:
            assert n.name

    def test_load_settlements(self) -> None:
        settlements = load_settlements(self.layer_paths["settlements"])
        assert len(settlements) > 0
        for s in settlements:
            assert s.id
            assert s.population >= 0

    def test_load_npcs(self) -> None:
        npcs = load_npcs(self.layer_paths["entities"], item_catalog=self.item_catalog)
        assert len(npcs) > 0
        for npc in npcs:
            assert npc.id
            assert npc.name
            assert isinstance(npc.role, NpcRole)
            # Brain is assigned by BrainFactory in GameService, not by content_loader
            assert npc.brain is None

    def test_item_catalog_loads(self) -> None:
        assert len(self.item_catalog) > 0
        for _entry_id, entry in self.item_catalog.items():
            assert entry.name
            assert entry.type
