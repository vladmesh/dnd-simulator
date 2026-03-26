"""Tests for world fork and delete operations."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.content_loader.assembly import (
    LAYER_ORDER,
    assemble_world,
    create_empty_world,
    fork_world,
)
from dnd_simulator.content_loader.manifest import LayerType, resolve_manifest
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


def _with_library(tmp_path: Path) -> Path:
    """Create a content dir that symlinks the real library for testing."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "worlds").mkdir()
    (content_dir / "library").symlink_to(CONTENT_DIR / "library")
    return content_dir


def _assemble_full(content_dir: Path, world_id: str) -> Path:
    return assemble_world(
        content_dir=content_dir,
        world_id=world_id,
        name="Test World",
        description="A test",
        layer_selections={lt.value: "sword_vale" for lt in LayerType},
        default_player_faction="kingdom",
    )


class TestForkWorld:
    def test_fork_creates_copy_with_same_layers(self, tmp_path: Path) -> None:
        """Fork creates a new world with identical layer references."""
        content_dir = _with_library(tmp_path)
        _assemble_full(content_dir, "original")

        fork_path = fork_world(content_dir, "original", "copy")
        assert fork_path.is_dir()

        with (fork_path / "manifest.yaml").open() as f:
            forked = yaml.safe_load(f)

        # All 5 layers present with same library references
        for lt in LayerType:
            assert forked["layers"][lt.value]["source"] == "library"
            assert forked["layers"][lt.value]["template"] == "sword_vale"

        # Original unchanged
        original_resolved = resolve_manifest(content_dir / "worlds" / "original", content_dir)
        assert len(original_resolved) == 5

    def test_fork_with_truncation(self, tmp_path: Path) -> None:
        """Fork with from_layer removes that layer and all above it."""
        content_dir = _with_library(tmp_path)
        _assemble_full(content_dir, "source")

        fork_path = fork_world(content_dir, "source", "truncated", from_layer=LayerType.SETTLEMENTS)

        resolved = resolve_manifest(fork_path, content_dir)
        assert set(resolved.keys()) == {"geography", "politics"}

        # Verify manifest has only 2 layers defined
        with (fork_path / "manifest.yaml").open() as f:
            manifest = yaml.safe_load(f)
        assert set(manifest["layers"].keys()) == {"geography", "politics"}

    def test_fork_conflict_raises(self, tmp_path: Path) -> None:
        """Forking to an existing world ID raises FileExistsError."""
        content_dir = _with_library(tmp_path)
        _assemble_full(content_dir, "src")
        _assemble_full(content_dir, "existing")

        with pytest.raises(FileExistsError):
            fork_world(content_dir, "src", "existing")

    def test_fork_source_not_found_raises(self, tmp_path: Path) -> None:
        """Forking a nonexistent world raises FileNotFoundError."""
        content_dir = _with_library(tmp_path)
        with pytest.raises(FileNotFoundError):
            fork_world(content_dir, "ghost", "copy")

    def test_fork_preserves_library_references(self, tmp_path: Path) -> None:
        """Forked manifest uses library source, no file copying."""
        content_dir = _with_library(tmp_path)
        _assemble_full(content_dir, "lib_src")

        fork_path = fork_world(content_dir, "lib_src", "lib_copy")

        with (fork_path / "manifest.yaml").open() as f:
            manifest = yaml.safe_load(f)

        for lt in LayerType:
            assert manifest["layers"][lt.value]["source"] == "library"
        # No custom layer directories copied
        for lt in LayerType:
            assert not (fork_path / lt.value).exists()

    def test_fork_from_geography_removes_all_layers(self, tmp_path: Path) -> None:
        """from_layer=geography removes ALL layers — empty manifest."""
        content_dir = _with_library(tmp_path)
        _assemble_full(content_dir, "full")

        fork_path = fork_world(content_dir, "full", "empty_fork", from_layer=LayerType.GEOGRAPHY)

        resolved = resolve_manifest(fork_path, content_dir)
        assert resolved == {}


class TestDeleteWorld:
    def test_delete_removes_directory(self, tmp_path: Path) -> None:
        """Deleting a world removes its directory; it disappears from list_worlds."""
        content_dir = _with_library(tmp_path)
        create_empty_world(content_dir, "doomed", "Doomed", "", "")

        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        assert any(w["id"] == "doomed" for w in service.list_worlds())

        service.delete_world("doomed")
        assert not any(w["id"] == "doomed" for w in service.list_worlds())
        assert not (content_dir / "worlds" / "doomed").exists()

    def test_delete_base_world_blocked(self) -> None:
        """Cannot delete a base world (sword_vale)."""
        store = JsonFileStore(CONTENT_DIR.parent / "saves")
        service = GameService(store=store, content_dir=CONTENT_DIR)
        with pytest.raises(ValueError, match="base world"):
            service.delete_world("sword_vale")

    def test_delete_world_blocked_if_active_session(self, tmp_path: Path) -> None:
        """Cannot delete a world with active sessions."""
        content_dir = _with_library(tmp_path)
        _assemble_full(content_dir, "active_world")

        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        service.start_game("active_world")

        with pytest.raises(RuntimeError, match="active session"):
            service.delete_world("active_world")


class TestForkDeleteApi:
    def _make_client(self, tmp_path: Path) -> TestClient:
        content_dir = _with_library(tmp_path)
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        set_service(service)
        return TestClient(app)

    def test_fork_endpoint(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        # Assemble source world
        client.post(
            "/api/master/worlds/assemble",
            json={
                "id": "fork_src",
                "name": "Fork Source",
                "description": "",
                "layer_selections": {lt.value: "sword_vale" for lt in LayerType},
                "default_player_faction": "kingdom",
            },
        )
        resp = client.post(
            "/api/master/worlds/fork_src/fork",
            json={"new_id": "fork_dst"},
        )
        assert resp.status_code == HTTPStatus.CREATED
        data = resp.json()
        assert data["id"] == "fork_dst"
        assert data["complete"] is True

    def test_fork_with_truncation_endpoint(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        client.post(
            "/api/master/worlds/assemble",
            json={
                "id": "trunc_src",
                "name": "Trunc Source",
                "description": "",
                "layer_selections": {lt.value: "sword_vale" for lt in LayerType},
                "default_player_faction": "kingdom",
            },
        )
        resp = client.post(
            "/api/master/worlds/trunc_src/fork",
            json={"new_id": "trunc_dst", "from_layer": "settlements"},
        )
        assert resp.status_code == HTTPStatus.CREATED
        data = resp.json()
        assert data["complete"] is False

    def test_delete_endpoint(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        client.post(
            "/api/master/worlds",
            json={"id": "del_me", "name": "Delete Me"},
        )
        resp = client.delete("/api/master/worlds/del_me")
        assert resp.status_code == HTTPStatus.OK

        # Confirm gone
        resp = client.get("/api/master/worlds")
        assert not any(w["id"] == "del_me" for w in resp.json())


class TestLayerOrder:
    def test_layer_order_contains_all_types(self) -> None:
        assert set(LAYER_ORDER) == set(LayerType)

    def test_layer_order_geography_first_entities_last(self) -> None:
        assert LAYER_ORDER[0] == LayerType.GEOGRAPHY
        assert LAYER_ORDER[-1] == LayerType.ENTITIES
