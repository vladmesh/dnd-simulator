"""Tests for partial manifest support, complete flag, and create_empty_world."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.content_loader.assembly import create_empty_world
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


def _make_partial_world(content_dir: Path, world_id: str, defined_layers: dict[str, dict[str, str]]) -> Path:
    """Create a world with only some layers defined in the manifest."""
    world_path = content_dir / "worlds" / world_id
    world_path.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": {"en": "Partial World"},
        "description": {"en": "A partial world for testing"},
        "default_player_faction": "kingdom",
        "layers": defined_layers,
    }
    with (world_path / "manifest.yaml").open("w") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return world_path


class TestPartialManifestResolution:
    def test_partial_manifest_resolves_defined_layers_only(self, tmp_path: Path) -> None:
        """Manifest with 2/5 layers defined resolves to dict with 2 entries."""
        content_dir = _with_library(tmp_path)
        world_path = _make_partial_world(
            content_dir,
            "partial",
            {
                "geography": {"source": "library", "template": "sword_vale", "version": "1.0"},
                "politics": {"source": "library", "template": "sword_vale", "version": "1.0"},
            },
        )
        result = resolve_manifest(world_path, content_dir)
        assert set(result.keys()) == {"geography", "politics"}

    def test_empty_manifest_resolves_to_empty_dict(self, tmp_path: Path) -> None:
        """Manifest with layers: {} resolves to empty dict."""
        content_dir = _with_library(tmp_path)
        world_path = _make_partial_world(content_dir, "empty_layers", {})
        result = resolve_manifest(world_path, content_dir)
        assert result == {}


class TestCompleteFlag:
    def test_complete_flag_full_world(self, tmp_path: Path) -> None:
        """list_worlds returns complete=True for a world with all 5 layers."""
        content_dir = _with_library(tmp_path)
        # Assemble a full world via the existing function
        from dnd_simulator.content_loader.assembly import assemble_world

        assemble_world(
            content_dir=content_dir,
            world_id="full",
            name="Full World",
            description="All layers",
            layer_selections={lt.value: "sword_vale" for lt in LayerType},
            default_player_faction="kingdom",
        )
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        worlds = service.list_worlds()
        full = next(w for w in worlds if w["id"] == "full")
        assert full["complete"] is True

    def test_complete_flag_partial_world(self, tmp_path: Path) -> None:
        """list_worlds returns complete=False for a world with 3/5 layers."""
        content_dir = _with_library(tmp_path)
        _make_partial_world(
            content_dir,
            "partial",
            {
                "geography": {"source": "library", "template": "sword_vale", "version": "1.0"},
                "politics": {"source": "library", "template": "sword_vale", "version": "1.0"},
                "ecology": {"source": "library", "template": "sword_vale", "version": "1.0"},
            },
        )
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        worlds = service.list_worlds()
        partial = next(w for w in worlds if w["id"] == "partial")
        assert partial["complete"] is False


class TestStartGameRejectsIncomplete:
    def test_start_game_rejected_for_incomplete_world(self, tmp_path: Path) -> None:
        """start_game raises RuntimeError for a world missing layers."""
        content_dir = _with_library(tmp_path)
        _make_partial_world(
            content_dir,
            "incomplete",
            {
                "geography": {"source": "library", "template": "sword_vale", "version": "1.0"},
            },
        )
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        with pytest.raises(RuntimeError, match="incomplete"):
            service.start_game("incomplete")


class TestCreateEmptyWorld:
    def test_create_empty_world(self, tmp_path: Path) -> None:
        """create_empty_world creates a world with no layers defined."""
        content_dir = _with_library(tmp_path)
        path = create_empty_world(content_dir, "blank", "Blank World", "A blank canvas", "kingdom")
        assert path.is_dir()
        assert (path / "manifest.yaml").exists()

        result = resolve_manifest(path, content_dir)
        assert result == {}

        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        worlds = service.list_worlds()
        blank = next(w for w in worlds if w["id"] == "blank")
        assert blank["complete"] is False

    def test_create_empty_world_duplicate_raises(self, tmp_path: Path) -> None:
        """Creating a world with an existing ID raises FileExistsError."""
        content_dir = _with_library(tmp_path)
        create_empty_world(content_dir, "dupe", "Dupe", "", "kingdom")
        with pytest.raises(FileExistsError):
            create_empty_world(content_dir, "dupe", "Dupe Again", "", "kingdom")


class TestGetWorldManifestPartial:
    def test_partial_world_returns_all_layer_types(self, tmp_path: Path) -> None:
        """get_world_manifest returns all 5 layer types, undefined ones with source=None."""
        content_dir = _with_library(tmp_path)
        _make_partial_world(
            content_dir,
            "partial_manifest",
            {
                "geography": {"source": "library", "template": "sword_vale", "version": "1.0"},
                "politics": {"source": "library", "template": "sword_vale", "version": "1.0"},
            },
        )
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        data = service.get_world_manifest("partial_manifest")
        layers = data["layers"]
        assert isinstance(layers, list)
        assert len(layers) == 5

        # Defined layers have source set
        geo = next(ly for ly in layers if ly["layer_type"] == "geography")
        assert geo["source"] == "library"
        assert geo["template"] == "sword_vale"

        # Undefined layers have source=None
        settlements = next(ly for ly in layers if ly["layer_type"] == "settlements")
        assert settlements["source"] is None
        assert settlements["template"] is None


class TestCreateEmptyWorldApi:
    def _make_client(self, tmp_path: Path) -> TestClient:
        content_dir = _with_library(tmp_path)
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        set_service(service)
        return TestClient(app)

    def test_create_empty_world_endpoint(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        resp = client.post(
            "/api/master/worlds",
            json={
                "id": "api_blank",
                "name": "API Blank",
                "description": "Created via API",
                "default_player_faction": "kingdom",
            },
        )
        assert resp.status_code == HTTPStatus.CREATED
        data = resp.json()
        assert data["id"] == "api_blank"
        assert data["name"] == "API Blank"
        assert data["complete"] is False

    def test_create_empty_world_duplicate_returns_409(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        payload = {
            "id": "dup_api",
            "name": "Dup",
            "description": "",
            "default_player_faction": "kingdom",
        }
        client.post("/api/master/worlds", json=payload)
        resp = client.post("/api/master/worlds", json=payload)
        assert resp.status_code == HTTPStatus.CONFLICT

    def test_list_worlds_includes_complete_field(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        # Create an empty world
        client.post(
            "/api/master/worlds",
            json={"id": "empty_listed", "name": "Empty", "description": "", "default_player_faction": ""},
        )
        resp = client.get("/api/master/worlds")
        assert resp.status_code == HTTPStatus.OK
        worlds = resp.json()
        empty = next(w for w in worlds if w["id"] == "empty_listed")
        assert "complete" in empty
        assert empty["complete"] is False
