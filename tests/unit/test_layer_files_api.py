"""Tests for layer files read/write API (service-level)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.content_loader.assembly import assemble_world, fork_layer
from dnd_simulator.content_loader.manifest import LayerType

CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / "content"


def _with_library(tmp_path: Path) -> Path:
    """Create a content dir that symlinks the real library for testing."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "worlds").mkdir()
    (content_dir / "library").symlink_to(CONTENT_DIR / "library")
    return content_dir


def _make_world(content_dir: Path, world_id: str = "test_world") -> Path:
    """Assemble a world from default library templates."""
    return assemble_world(
        content_dir=content_dir,
        world_id=world_id,
        name="Test World",
        description="A test world",
        layer_selections={lt.value: "sword_vale" for lt in LayerType},
        default_player_faction="kingdom",
    )


class TestGetLayerFiles:
    """GET layer files — list all data files with contents."""

    def test_read_files_from_custom_layer(self, tmp_path: Path) -> None:
        """Fork a layer, read its files — get dict of filename→content, no metadata.yaml."""
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        content_dir = _with_library(tmp_path)
        _make_world(content_dir)
        fork_layer(content_dir, "test_world", LayerType.ENTITIES)

        service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)
        files = service.get_layer_files("test_world", LayerType.ENTITIES)

        assert isinstance(files, dict)
        assert "npcs.yaml" in files
        assert "metadata.yaml" not in files
        # Content should be non-empty YAML strings
        assert len(files["npcs.yaml"]) > 0

    def test_read_files_from_library_layer(self, tmp_path: Path) -> None:
        """Reading library layers works fine — read is allowed for both sources."""
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        content_dir = _with_library(tmp_path)
        _make_world(content_dir)

        service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)
        files = service.get_layer_files("test_world", LayerType.GEOGRAPHY)

        assert "regions.yaml" in files
        assert "locations.yaml" in files
        assert "metadata.yaml" not in files


class TestGetLayerFile:
    """GET single layer file."""

    def test_read_single_file(self, tmp_path: Path) -> None:
        """Read a specific file by name."""
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        content_dir = _with_library(tmp_path)
        _make_world(content_dir)

        service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)
        content = service.get_layer_file("test_world", LayerType.GEOGRAPHY, "regions.yaml")

        assert isinstance(content, str)
        assert len(content) > 0
        assert "silverport" in content.lower()

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Reading a nonexistent file raises FileNotFoundError."""
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        content_dir = _with_library(tmp_path)
        _make_world(content_dir)

        service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)
        with pytest.raises(FileNotFoundError):
            service.get_layer_file("test_world", LayerType.GEOGRAPHY, "nonexistent.yaml")


class TestUpdateLayerFile:
    """PUT layer file — write content to custom layers only."""

    def test_write_to_custom_layer(self, tmp_path: Path) -> None:
        """Write new content to a custom layer file, re-read confirms change."""
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        content_dir = _with_library(tmp_path)
        _make_world(content_dir)
        fork_layer(content_dir, "test_world", LayerType.ENTITIES)

        service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)

        new_content = "- id: test_npc\n  name: Modified NPC\n"
        service.update_layer_file("test_world", LayerType.ENTITIES, "npcs.yaml", new_content)

        # Re-read to confirm persistence
        result = service.get_layer_file("test_world", LayerType.ENTITIES, "npcs.yaml")
        assert result == new_content

    def test_write_to_library_layer_rejected(self, tmp_path: Path) -> None:
        """Writing to a library layer raises ValueError."""
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        content_dir = _with_library(tmp_path)
        _make_world(content_dir)

        service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)
        with pytest.raises(ValueError, match="library"):
            service.update_layer_file("test_world", LayerType.GEOGRAPHY, "regions.yaml", "test: data\n")

    def test_write_invalid_yaml_rejected(self, tmp_path: Path) -> None:
        """Writing invalid YAML raises ValueError with parse error."""
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        content_dir = _with_library(tmp_path)
        _make_world(content_dir)
        fork_layer(content_dir, "test_world", LayerType.ENTITIES)

        service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)
        with pytest.raises(ValueError, match="YAML"):
            service.update_layer_file("test_world", LayerType.ENTITIES, "npcs.yaml", "{{invalid: yaml: [")

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        """Filenames with path traversal components raise ValueError."""
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        content_dir = _with_library(tmp_path)
        _make_world(content_dir)
        fork_layer(content_dir, "test_world", LayerType.ENTITIES)

        service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)

        bad_names = ["../evil.yaml", "foo/bar.yaml", ".hidden", "no_extension", "test.txt"]
        for bad_name in bad_names:
            with pytest.raises(ValueError, match="filename"):
                service.update_layer_file("test_world", LayerType.ENTITIES, bad_name, "test: data\n")

    def test_path_traversal_rejected_on_read(self, tmp_path: Path) -> None:
        """Path traversal is also rejected on single-file reads."""
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        content_dir = _with_library(tmp_path)
        _make_world(content_dir)

        service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)
        with pytest.raises(ValueError, match="filename"):
            service.get_layer_file("test_world", LayerType.GEOGRAPHY, "../manifest.yaml")

    def test_world_not_found(self, tmp_path: Path) -> None:
        """Operations on nonexistent world raise FileNotFoundError."""
        from dnd_simulator.service.game_service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        content_dir = _with_library(tmp_path)
        service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)

        with pytest.raises(FileNotFoundError):
            service.get_layer_files("ghost_world", LayerType.GEOGRAPHY)
