"""Tests for directory-based world loading."""

from __future__ import annotations

from pathlib import Path

from dnd_simulator.content_loader import (
    load_nations,
    load_npcs,
    load_settlements,
    load_world,
    load_world_meta,
)

SWORD_VALE = Path(__file__).resolve().parents[1] / "content" / "worlds" / "sword_vale"


class TestDirectoryFormat:
    def test_load_world_meta(self) -> None:
        meta = load_world_meta(SWORD_VALE)
        assert meta["name"] == "Sword Vale"
        assert "Silverport" in meta["description"]

    def test_load_regions(self) -> None:
        regions = load_world(SWORD_VALE)
        assert len(regions) == 7
        ids = {r.id for r in regions}
        assert "silverport" in ids
        assert "frostholm" in ids

    def test_load_nations(self) -> None:
        nations = load_nations(SWORD_VALE)
        assert len(nations) == 3
        names = {n.name for n in nations}
        assert "Kingdom of Silverhold" in names

    def test_load_settlements(self) -> None:
        settlements = load_settlements(SWORD_VALE)
        assert len(settlements) > 0
        city = next(s for s in settlements if s.id == "silverport_city")
        assert city.population == 5000

    def test_load_npcs(self) -> None:
        npcs = load_npcs(SWORD_VALE)
        assert len(npcs) == 3
        edgar = next(n for n in npcs if n.id == "edgar")
        assert edgar.role == "blacksmith"
        assert edgar.brain is not None
