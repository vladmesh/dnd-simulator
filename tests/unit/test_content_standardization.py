"""Tests for converted directory-format worlds (Phase 1 — Content Standardization).

Verifies that arena, village, and sneak_test load correctly from directory format
with expected entity counts, IDs, and properties.
"""

from __future__ import annotations

from pathlib import Path

from dnd_simulator.content_loader import (
    load_battle_maps,
    load_locations,
    load_npcs,
    load_settlements,
    load_world,
    load_world_meta,
)

WORLDS = Path(__file__).resolve().parents[2] / "content" / "worlds"


class TestArenaDirectory:
    """Blood Arena: 1 region, 1 location, 4 NPCs, battle map 80x80 with 4 walls."""

    path = WORLDS / "arena"

    def test_meta(self) -> None:
        meta = load_world_meta(self.path)
        assert meta["name"] == "Blood Arena"
        assert "gladiatorial" in meta["description"]

    def test_regions(self) -> None:
        regions = load_world(self.path)
        assert len(regions) == 1
        assert regions[0].id == "arena"

    def test_locations(self) -> None:
        regions = load_world(self.path)
        locations = load_locations(self.path, regions)
        assert len(locations) == 1
        assert locations[0].id == "arena_floor"
        assert locations[0].region_id == "arena"

    def test_npcs(self) -> None:
        npcs = load_npcs(self.path)
        assert len(npcs) == 4
        ids = {n.id for n in npcs}
        assert ids == {"razor", "shadow", "iron", "paladin"}

    def test_paladin_is_llm(self) -> None:
        npcs = load_npcs(self.path)
        paladin = next(n for n in npcs if n.id == "paladin")
        assert paladin.ai_type == "llm"

    def test_battle_map(self) -> None:
        maps = load_battle_maps(self.path)
        assert "arena" in maps
        bm = maps["arena"]
        assert bm.width == 80
        assert bm.height == 80
        # 4 authored walls + 4 boundary walls added by BattleMap
        assert len(bm.walls) == 8


class TestVillageDirectory:
    """Quiet Village: 1 region, 8 locations, 5 NPCs, 1 settlement."""

    path = WORLDS / "village"

    def test_meta(self) -> None:
        meta = load_world_meta(self.path)
        assert meta["name"] == "Quiet Village"

    def test_regions(self) -> None:
        regions = load_world(self.path)
        assert len(regions) == 1
        assert regions[0].id == "village"

    def test_locations(self) -> None:
        regions = load_world(self.path)
        locations = load_locations(self.path, regions)
        assert len(locations) == 8
        ids = {loc.id for loc in locations}
        assert "village_square" in ids
        assert "millbrook_tavern" in ids

    def test_npcs(self) -> None:
        npcs = load_npcs(self.path)
        assert len(npcs) == 5
        ids = {n.id for n in npcs}
        assert ids == {"olga", "sergei", "masha", "ivan", "tanya"}

    def test_settlements(self) -> None:
        settlements = load_settlements(self.path)
        assert len(settlements) == 1
        assert settlements[0].id == "millbrook"
        assert settlements[0].population == 120

    def test_merchant_has_items(self) -> None:
        npcs = load_npcs(self.path)
        masha = next(n for n in npcs if n.id == "masha")
        assert masha.gold == 200
        assert len(masha.inventory) > 0


class TestSneakTestDirectory:
    """Sneak Test: 1 region, 1 location, 1 NPC, battle map 40x40."""

    path = WORLDS / "sneak_test"

    def test_meta(self) -> None:
        meta = load_world_meta(self.path)
        assert meta["name"] == "Sneak Attack Test"

    def test_regions(self) -> None:
        regions = load_world(self.path)
        assert len(regions) == 1
        assert regions[0].id == "test_arena"

    def test_locations(self) -> None:
        regions = load_world(self.path)
        locations = load_locations(self.path, regions)
        assert len(locations) == 1
        assert locations[0].id == "test_floor"

    def test_npcs(self) -> None:
        npcs = load_npcs(self.path)
        assert len(npcs) == 1
        assert npcs[0].id == "dummy"
        assert npcs[0].max_hp == 50

    def test_battle_map(self) -> None:
        maps = load_battle_maps(self.path)
        assert "test_arena" in maps
        bm = maps["test_arena"]
        assert bm.width == 40
        assert bm.height == 40
        # 0 authored walls + 4 boundary walls added by BattleMap
        assert len(bm.walls) == 4
