"""Tests for legacy loading code removal (Sprint 005, Phase 1, Task 2).

Verifies that legacy fallback aliases are gone and only the canonical
directory-based loading paths remain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dnd_simulator.content_loader import parse_npc, parse_player

WORLDS = Path(__file__).resolve().parents[2] / "content" / "worlds"


class TestParseNpcNoLegacy:
    """parse_npc uses start_location only, no region_id fallback."""

    def test_start_location_works(self) -> None:
        ndata: dict[str, Any] = {
            "name": "Test NPC",
            "race": "human",
            "class": "commoner",
            "start_location": "tavern",
        }
        npc = parse_npc("test_npc", ndata)
        assert npc.location_id == "tavern"

    def test_region_id_not_used_as_fallback(self) -> None:
        """region_id should NOT be picked up as a fallback for location."""
        ndata: dict[str, Any] = {
            "name": "Test NPC",
            "race": "human",
            "class": "commoner",
            "region_id": "some_region",
        }
        npc = parse_npc("test_npc", ndata)
        # Without start_location, location_id should be empty — NOT "some_region"
        assert npc.location_id == ""

    def test_start_location_required_for_known_locations_check(self) -> None:
        """With known_locations, start_location is what gets validated."""
        ndata: dict[str, Any] = {
            "name": "Test NPC",
            "race": "human",
            "class": "commoner",
            "start_location": "tavern",
        }
        npc = parse_npc("test_npc", ndata, known_locations={"tavern", "square"})
        assert npc.location_id == "tavern"


class TestParsePlayerNoLegacy:
    """parse_player uses start_location only, no start_region/location_id fallback."""

    def test_start_location_works(self) -> None:
        pdata: dict[str, Any] = {
            "name": "Hero",
            "race": "human",
            "class": "fighter",
            "start_location": "village_square",
        }
        player = parse_player(pdata)
        assert player.location_id == "village_square"

    def test_legacy_start_region_not_used(self) -> None:
        """start_region should NOT be picked up as a fallback."""
        pdata: dict[str, Any] = {
            "name": "Hero",
            "race": "human",
            "class": "fighter",
            "start_region": "some_region",
        }
        player = parse_player(pdata)
        assert player.location_id == ""

    def test_legacy_location_id_not_used(self) -> None:
        """location_id in YAML should NOT be picked up as a fallback."""
        pdata: dict[str, Any] = {
            "name": "Hero",
            "race": "human",
            "class": "fighter",
            "location_id": "old_loc",
        }
        player = parse_player(pdata)
        # location_id in YAML data is NOT the same as the resulting .location_id attribute
        # It should only come from start_location
        assert player.location_id == ""


class TestParseSpawnNoLegacy:
    """_parse_spawn uses start_location only, no region_id fallback."""

    def test_start_location_works(self) -> None:
        from dnd_simulator.service.commands_creatures import _parse_spawn

        data: dict[str, Any] = {
            "id": "goblin_1",
            "name": "Goblin",
            "entity_type": "monster",
            "start_location": "cave_entrance",
            "hp": 7,
            "ac": 15,
            "speed": 30,
        }
        creature = _parse_spawn(data)
        assert creature.location_id == "cave_entrance"

    def test_region_id_raises_without_start_location(self) -> None:
        """Without start_location, should raise KeyError — no region_id fallback."""
        from dnd_simulator.service.commands_creatures import _parse_spawn

        data: dict[str, Any] = {
            "id": "goblin_1",
            "name": "Goblin",
            "entity_type": "monster",
            "region_id": "forest",
            "hp": 7,
            "ac": 15,
            "speed": 30,
        }
        with pytest.raises(KeyError):
            _parse_spawn(data)


class TestSchemaNoLegacy:
    """Pydantic schemas should not have legacy alias fields."""

    def test_create_player_no_start_region(self) -> None:
        from dnd_simulator.adapters.api.schemas import CreatePlayerRequest

        fields = set(CreatePlayerRequest.model_fields.keys())
        assert "start_region" not in fields

    def test_spawn_creature_no_region_id(self) -> None:
        from dnd_simulator.adapters.api.schemas import SpawnCreatureRequest

        fields = set(SpawnCreatureRequest.model_fields.keys())
        assert "region_id" not in fields


class TestListWorldsDirectoryOnly:
    """list_worlds should only pick up directories with manifest.yaml, not stray files."""

    def test_ignores_stray_yaml_files(self, tmp_path: Path) -> None:
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        worlds_dir = tmp_path / "content" / "worlds"
        worlds_dir.mkdir(parents=True)

        # Create a proper directory world with manifest.yaml
        good_world = worlds_dir / "test_world"
        good_world.mkdir()
        (good_world / "manifest.yaml").write_text("name: Test World\ndescription: A test\nlayers: {}\n")

        # Create a stray .yaml file (should be ignored)
        (worlds_dir / "stray.yaml").write_text("name: Stray\n")

        store = JsonFileStore(tmp_path / "saves")
        svc = GameService(store=store, content_dir=tmp_path / "content")
        worlds = svc.list_worlds()

        world_ids = [w["id"] for w in worlds]
        assert "test_world" in world_ids
        assert "stray.yaml" not in world_ids


class TestResolveSourceRemoved:
    """_resolve_source should be removed — import should fail."""

    def test_no_resolve_source(self) -> None:
        with pytest.raises(ImportError):
            from dnd_simulator.content_loader import _resolve_source  # noqa: F401


class TestLoadSectionSimplified:
    """_load_section should only accept a directory path, no is_dir parameter."""

    def test_load_section_no_is_dir_param(self) -> None:
        import inspect

        from dnd_simulator.content_loader import _load_section

        sig = inspect.signature(_load_section)
        # Should only take (path, section), no is_dir
        assert "is_dir" not in sig.parameters
