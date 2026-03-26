"""Tests for layer scaffolding — creating minimal valid custom layers from scratch."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.content_loader.assembly import create_empty_world, scaffold_layer
from dnd_simulator.content_loader.manifest import LayerSource, LayerType, resolve_manifest
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


class TestScaffoldLayer:
    def test_scaffold_geography_creates_valid_files(self, tmp_path: Path) -> None:
        """Scaffold geography creates regions.yaml and locations.yaml, updates manifest."""
        content_dir = _make_content(tmp_path)
        _create_empty(content_dir, "geo_test")

        scaffold_layer(content_dir, "geo_test", LayerType.GEOGRAPHY)

        layer_dir = content_dir / "worlds" / "geo_test" / "geography"
        assert layer_dir.is_dir()
        assert (layer_dir / "regions.yaml").exists()
        assert (layer_dir / "locations.yaml").exists()

        # Files are valid YAML
        for f in layer_dir.glob("*.yaml"):
            yaml.safe_load(f.read_text())

        # Manifest updated
        manifest = _read_manifest(content_dir, "geo_test")
        assert manifest["layers"]["geography"]["source"] == "custom"
        assert "template" not in manifest["layers"]["geography"]

    def test_scaffold_all_layers_makes_world_complete(self, tmp_path: Path) -> None:
        """Create empty world, scaffold all 5 layers → complete flag true, session starts."""
        content_dir = _make_content(tmp_path)
        _create_empty(content_dir, "full_scaffold")

        for lt in LayerType:
            scaffold_layer(content_dir, "full_scaffold", lt)

        # Resolves all 5 layers
        resolved = resolve_manifest(content_dir / "worlds" / "full_scaffold", content_dir)
        assert set(resolved.keys()) == {lt.value for lt in LayerType}

        # Start a session — empty but no crash
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        session = service.start_game("full_scaffold")
        assert session.world is not None
        assert len(session.world.layers) == 5

    def test_scaffold_already_defined_layer_raises(self, tmp_path: Path) -> None:
        """Scaffold on a layer that already has a source raises ValueError."""
        content_dir = _make_content(tmp_path)
        _create_empty(content_dir, "dupe_layer")
        scaffold_layer(content_dir, "dupe_layer", LayerType.GEOGRAPHY)

        with pytest.raises(ValueError, match="already defined"):
            scaffold_layer(content_dir, "dupe_layer", LayerType.GEOGRAPHY)

    def test_scaffold_nonexistent_world_raises(self, tmp_path: Path) -> None:
        """Scaffold on a world that doesn't exist raises FileNotFoundError."""
        content_dir = _make_content(tmp_path)

        with pytest.raises(FileNotFoundError):
            scaffold_layer(content_dir, "ghost", LayerType.GEOGRAPHY)

    def test_scaffold_updates_manifest_correctly(self, tmp_path: Path) -> None:
        """After scaffold, get_world_manifest shows layer as source: custom."""
        content_dir = _make_content(tmp_path)
        _create_empty(content_dir, "manifest_check")
        scaffold_layer(content_dir, "manifest_check", LayerType.SETTLEMENTS)

        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        data = service.get_world_manifest("manifest_check")
        layers = data["layers"]
        assert isinstance(layers, list)

        settlements_layer = next(ly for ly in layers if ly["layer_type"] == "settlements")
        assert settlements_layer["source"] == LayerSource.CUSTOM
        assert settlements_layer["template"] is None
        assert settlements_layer["version"] is None

    def test_scaffolded_ecology_has_correct_structure(self, tmp_path: Path) -> None:
        """Ecology scaffold has monsters.yaml with templates and encounters keys."""
        content_dir = _make_content(tmp_path)
        _create_empty(content_dir, "eco_test")

        scaffold_layer(content_dir, "eco_test", LayerType.ECOLOGY)

        monsters_path = content_dir / "worlds" / "eco_test" / "ecology" / "monsters.yaml"
        assert monsters_path.exists()
        data = yaml.safe_load(monsters_path.read_text())
        assert "templates" in data
        assert "encounters" in data

    def test_full_pipeline_create_scaffold_fork_start(self, tmp_path: Path) -> None:
        """Golden path: create empty → scaffold all → fork a layer → edit → start session."""
        content_dir = _make_content(tmp_path)
        _create_empty(content_dir, "pipeline")

        # Scaffold all layers
        for lt in LayerType:
            scaffold_layer(content_dir, "pipeline", lt)

        # Fork entities layer (already custom from scaffold — but let's test fork_world + scaffold combo)
        # Actually, scaffold already creates custom layers. Test the fork_world → scaffold path instead.
        from dnd_simulator.content_loader.assembly import fork_world

        fork_world(content_dir, "pipeline", "pipeline_fork", from_layer=LayerType.ENTITIES)
        scaffold_layer(content_dir, "pipeline_fork", LayerType.ENTITIES)

        # Edit a scaffolded file
        npcs_path = content_dir / "worlds" / "pipeline_fork" / "entities" / "npcs.yaml"
        npcs_path.write_text("")  # empty is valid

        # Start session
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        session = service.start_game("pipeline_fork")
        assert session.world is not None


class TestScaffoldApi:
    def _make_client(self, tmp_path: Path) -> TestClient:
        content_dir = _make_content(tmp_path)
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store, content_dir=content_dir)
        set_service(service)
        return TestClient(app)

    def test_scaffold_endpoint_creates_layer(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        # Create empty world first
        client.post("/api/master/worlds", json={"id": "api_scaf", "name": "API Scaffold"})

        resp = client.post("/api/master/worlds/api_scaf/layers/geography/scaffold")
        assert resp.status_code == HTTPStatus.CREATED

    def test_scaffold_nonexistent_world_returns_404(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        resp = client.post("/api/master/worlds/nope/layers/geography/scaffold")
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_scaffold_already_defined_returns_409(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        client.post("/api/master/worlds", json={"id": "api_dupe", "name": "Dupe"})
        client.post("/api/master/worlds/api_dupe/layers/geography/scaffold")

        resp = client.post("/api/master/worlds/api_dupe/layers/geography/scaffold")
        assert resp.status_code == HTTPStatus.CONFLICT


# -- Helpers --


def _make_content(tmp_path: Path) -> Path:
    """Create a content dir with symlinked library."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "worlds").mkdir()
    (content_dir / "library").symlink_to(CONTENT_DIR / "library")
    catalogs_src = CONTENT_DIR / "catalogs"
    if catalogs_src.exists():
        (content_dir / "catalogs").symlink_to(catalogs_src)
    return content_dir


def _create_empty(content_dir: Path, world_id: str) -> Path:
    return create_empty_world(content_dir, world_id, "Test", "", "")


def _read_manifest(content_dir: Path, world_id: str) -> dict:  # type: ignore[type-arg]
    with (content_dir / "worlds" / world_id / "manifest.yaml").open() as f:
        return yaml.safe_load(f)
