"""Tests for directory-based world loading via manifest resolution."""

from __future__ import annotations

from pathlib import Path

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
LAYER_PATHS = resolve_manifest(SWORD_VALE, CONTENT_DIR)
_ITEM_CATALOG_DIR = CONTENT_DIR / "catalogs" / "items"
ITEM_CATALOG = load_catalog(_ITEM_CATALOG_DIR, ItemContent) if _ITEM_CATALOG_DIR.exists() else {}


class TestDirectoryFormat:
    def test_load_world_meta(self) -> None:
        meta = load_world_meta_from_manifest(SWORD_VALE)
        assert meta["name"] == "Sword Vale"
        assert "Silverport" in meta["description"]

    def test_load_regions(self) -> None:
        regions = load_world(LAYER_PATHS["geography"])
        assert len(regions) == 7
        ids = {r.id for r in regions}
        assert "silverport" in ids
        assert "frostholm" in ids

    def test_load_nations(self) -> None:
        nations = load_nations(LAYER_PATHS["politics"])
        assert len(nations) == 3
        names = {n.name for n in nations}
        assert "Kingdom of Silverhold" in names

    def test_load_settlements(self) -> None:
        settlements = load_settlements(LAYER_PATHS["settlements"])
        assert len(settlements) == 10
        city = next(s for s in settlements if s.id == "silverport_city")
        assert city.population == 5000

    def test_load_npcs(self) -> None:
        npcs = load_npcs(LAYER_PATHS["entities"], item_catalog=ITEM_CATALOG)
        assert len(npcs) == 4
        edgar = next(n for n in npcs if n.id == "edgar")
        assert edgar.role == NpcRole.BLACKSMITH
        assert edgar.ai_type == "rule_based"
        # Brain is assigned by BrainFactory in GameService, not by content_loader
        assert edgar.brain is None
