"""Tests for world assembly and fork — creating worlds from library templates."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.content_loader.assembly import assemble_world, fork_layer
from dnd_simulator.content_loader.manifest import LayerType, resolve_manifest
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

# Use the real content dir so we can assemble worlds from actual library templates
CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


class TestAssembleWorld:
    def test_creates_world_directory_with_manifest(self, tmp_path: Path) -> None:
        """Assembling a world creates a directory with a valid manifest.yaml."""
        content_dir = _with_library(tmp_path)
        world_path = assemble_world(
            content_dir=content_dir,
            world_id="my_world",
            name="My World",
            description="A test world",
            layer_selections={lt.value: "sword_vale" for lt in LayerType},
            default_player_faction="kingdom",
        )
        assert world_path.is_dir()
        assert (world_path / "manifest.yaml").exists()

        with (world_path / "manifest.yaml").open() as f:
            manifest = yaml.safe_load(f)

        assert manifest["name"] == "My World"
        assert manifest["description"] == "A test world"
        assert manifest["default_player_faction"] == "kingdom"
        for lt in LayerType:
            layer = manifest["layers"][lt.value]
            assert layer["source"] == "library"
            assert layer["template"] == "sword_vale"

    def test_assembled_world_resolves_via_manifest(self, tmp_path: Path) -> None:
        """An assembled world can be resolved by the existing manifest resolver."""
        content_dir = _with_library(tmp_path)
        world_path = assemble_world(
            content_dir=content_dir,
            world_id="resolving_world",
            name="Resolving World",
            description="",
            layer_selections={lt.value: "sword_vale" for lt in LayerType},
            default_player_faction="",
        )
        result = resolve_manifest(world_path, content_dir)
        assert set(result.keys()) == {lt.value for lt in LayerType}
        for path in result.values():
            assert path.is_dir()

    def test_assembled_world_starts_session(self) -> None:
        """A session can be started from an assembled world (using real content)."""
        store = JsonFileStore(CONTENT_DIR.parent / "saves")
        service = GameService(store=store, content_dir=CONTENT_DIR)
        # Assemble into a temp area — but we need the assembled world to be under
        # the same content_dir the service uses. Use the service method instead.
        service.assemble_world(
            world_id="session_test_world",
            name="Session Test",
            description="",
            layer_selections={lt.value: "sword_vale" for lt in LayerType},
            default_player_faction="kingdom",
        )
        try:
            session = service.start_game("session_test_world")
            assert session.world is not None
            assert len(session.world.layers) == 5
        finally:
            # Cleanup: remove the assembled world dir
            import shutil

            world_path = CONTENT_DIR / "worlds" / "session_test_world"
            if world_path.exists():
                shutil.rmtree(world_path)

    def test_assembled_world_in_list_worlds(self, tmp_path: Path) -> None:
        content_dir = _with_library(tmp_path)
        assemble_world(
            content_dir=content_dir,
            world_id="listed_world",
            name="Listed World",
            description="Should appear in list",
            layer_selections={lt.value: "sword_vale" for lt in LayerType},
            default_player_faction="",
        )
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        worlds = service.list_worlds()
        assert any(w["id"] == "listed_world" for w in worlds)


class TestAssembleValidation:
    def test_missing_layer_type_raises(self, tmp_path: Path) -> None:
        content_dir = _with_library(tmp_path)
        incomplete = {lt.value: "sword_vale" for lt in LayerType}
        del incomplete["entities"]
        with pytest.raises(RuntimeError, match="entities"):
            assemble_world(
                content_dir=content_dir,
                world_id="bad",
                name="Bad",
                description="",
                layer_selections=incomplete,
                default_player_faction="",
            )

    def test_nonexistent_template_raises(self, tmp_path: Path) -> None:
        content_dir = _with_library(tmp_path)
        selections = {lt.value: "sword_vale" for lt in LayerType}
        selections["geography"] = "nonexistent"
        with pytest.raises(RuntimeError, match="nonexistent"):
            assemble_world(
                content_dir=content_dir,
                world_id="bad",
                name="Bad",
                description="",
                layer_selections=selections,
                default_player_faction="",
            )

    def test_existing_world_raises(self, tmp_path: Path) -> None:
        content_dir = _with_library(tmp_path)
        selections = {lt.value: "sword_vale" for lt in LayerType}
        assemble_world(
            content_dir=content_dir,
            world_id="dupe",
            name="Dupe",
            description="",
            layer_selections=selections,
            default_player_faction="",
        )
        with pytest.raises(FileExistsError):
            assemble_world(
                content_dir=content_dir,
                world_id="dupe",
                name="Dupe Again",
                description="",
                layer_selections=selections,
                default_player_faction="",
            )


class TestForkLayer:
    def test_fork_copies_files_and_updates_manifest(self, tmp_path: Path) -> None:
        content_dir = _with_library(tmp_path)
        selections = {lt.value: "sword_vale" for lt in LayerType}
        world_path = assemble_world(
            content_dir=content_dir,
            world_id="forkable",
            name="Forkable",
            description="",
            layer_selections=selections,
            default_player_faction="",
        )

        forked_path = fork_layer(content_dir, "forkable", LayerType.ENTITIES)

        # Files copied
        assert forked_path.is_dir()
        assert (forked_path / "npcs.yaml").exists()

        # Manifest updated
        with (world_path / "manifest.yaml").open() as f:
            manifest = yaml.safe_load(f)
        assert manifest["layers"]["entities"]["source"] == "custom"
        # Other layers still library
        assert manifest["layers"]["geography"]["source"] == "library"
        assert manifest["layers"]["politics"]["source"] == "library"

    def test_fork_still_resolves(self, tmp_path: Path) -> None:
        content_dir = _with_library(tmp_path)
        selections = {lt.value: "sword_vale" for lt in LayerType}
        world_path = assemble_world(
            content_dir=content_dir,
            world_id="fork_resolve",
            name="Fork Resolve",
            description="",
            layer_selections=selections,
            default_player_faction="",
        )
        fork_layer(content_dir, "fork_resolve", LayerType.ENTITIES)

        result = resolve_manifest(world_path, content_dir)
        # Entities should now point to the custom dir
        assert result["entities"] == world_path / "entities"
        # Geography still points to library
        assert "library" in str(result["geography"])

    def test_fork_already_custom_raises(self, tmp_path: Path) -> None:
        content_dir = _with_library(tmp_path)
        selections = {lt.value: "sword_vale" for lt in LayerType}
        assemble_world(
            content_dir=content_dir,
            world_id="double_fork",
            name="Double Fork",
            description="",
            layer_selections=selections,
            default_player_faction="",
        )
        fork_layer(content_dir, "double_fork", LayerType.ENTITIES)
        with pytest.raises(ValueError, match="already custom"):
            fork_layer(content_dir, "double_fork", LayerType.ENTITIES)

    def test_fork_nonexistent_world_raises(self, tmp_path: Path) -> None:
        content_dir = _with_library(tmp_path)
        with pytest.raises(FileNotFoundError):
            fork_layer(content_dir, "ghost_world", LayerType.GEOGRAPHY)


class TestAssemblyApi:
    def _make_client(self, tmp_path: Path) -> TestClient:
        content_dir = _with_library(tmp_path)
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        set_service(service)
        return TestClient(app)

    def test_assemble_world_endpoint(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        resp = client.post(
            "/api/master/worlds/assemble",
            json={
                "id": "api_world",
                "name": "API World",
                "description": "Created via API",
                "layer_selections": {lt.value: "sword_vale" for lt in LayerType},
                "default_player_faction": "kingdom",
            },
        )
        assert resp.status_code == HTTPStatus.CREATED
        data = resp.json()
        assert data["id"] == "api_world"
        assert data["name"] == "API World"

    def test_assemble_then_list(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        client.post(
            "/api/master/worlds/assemble",
            json={
                "id": "listed_api",
                "name": "Listed API",
                "description": "",
                "layer_selections": {lt.value: "sword_vale" for lt in LayerType},
                "default_player_faction": "",
            },
        )
        resp = client.get("/api/master/worlds")
        assert resp.status_code == HTTPStatus.OK
        assert any(w["id"] == "listed_api" for w in resp.json())

    def test_fork_endpoint(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        # First assemble
        client.post(
            "/api/master/worlds/assemble",
            json={
                "id": "fork_api",
                "name": "Fork API",
                "description": "",
                "layer_selections": {lt.value: "sword_vale" for lt in LayerType},
                "default_player_faction": "",
            },
        )
        # Then fork entities
        resp = client.post("/api/master/worlds/fork_api/fork/entities")
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert "entities" in data["message"].lower() or "custom" in data["message"].lower()

    def test_fork_already_custom_returns_409(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        client.post(
            "/api/master/worlds/assemble",
            json={
                "id": "fork_409",
                "name": "Fork 409",
                "description": "",
                "layer_selections": {lt.value: "sword_vale" for lt in LayerType},
                "default_player_faction": "",
            },
        )
        client.post("/api/master/worlds/fork_409/fork/entities")
        resp = client.post("/api/master/worlds/fork_409/fork/entities")
        assert resp.status_code == HTTPStatus.CONFLICT

    def test_old_create_world_endpoint_gone(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        resp = client.post("/api/master/worlds", json={"id": "x", "name": "X"})
        # Should be 405 (Method Not Allowed) or 404, not 201/200
        assert resp.status_code in (HTTPStatus.METHOD_NOT_ALLOWED, HTTPStatus.NOT_FOUND)

    def test_old_update_world_endpoint_gone(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        resp = client.put("/api/master/worlds/sword_vale", json={"id": "sword_vale", "name": "X"})
        assert resp.status_code in (HTTPStatus.METHOD_NOT_ALLOWED, HTTPStatus.NOT_FOUND)


def _with_library(tmp_path: Path) -> Path:
    """Create a content dir that symlinks the real library for testing."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "worlds").mkdir()
    # Symlink the real library so templates are available
    (content_dir / "library").symlink_to(CONTENT_DIR / "library")
    return content_dir
