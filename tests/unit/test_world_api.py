"""Tests for world-management REST routes (``adapters/api/routes_world.py``)."""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.content_loader.assembly import assemble_world, fork_layer
from dnd_simulator.content_loader.manifest import LayerType
from dnd_simulator.i18n import current_lang, set_language
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / "content"
_ALL_SWORD_VALE = {lt.value: "sword_vale" for lt in LayerType}


@pytest.fixture(autouse=True)
def _english() -> Iterator[None]:
    previous = current_lang.get()
    set_language("en")
    yield
    set_language(previous)


def _content_dir(tmp_path: Path) -> Path:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "worlds").mkdir()
    (content_dir / "library").symlink_to(CONTENT_DIR / "library")
    catalogs_src = CONTENT_DIR / "catalogs"
    if catalogs_src.exists():
        (content_dir / "catalogs").symlink_to(catalogs_src)
    return content_dir


def _make_world(content_dir: Path, world_id: str = "test_world") -> None:
    assemble_world(
        content_dir=content_dir,
        world_id=world_id,
        name="Test World",
        description="A test world",
        layer_selections=_ALL_SWORD_VALE,
        default_player_faction="kingdom",
    )


@pytest.fixture
def env(tmp_path: Path) -> tuple[TestClient, GameService, Path]:
    content_dir = _content_dir(tmp_path)
    _make_world(content_dir)
    service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)
    set_service(service)
    return TestClient(app), service, content_dir


class TestLibrary:
    def test_list_templates(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/library/geography")
        assert resp.status_code == HTTPStatus.OK
        slugs = [t["slug"] for t in resp.json()]
        assert "sword_vale" in slugs
        item = next(t for t in resp.json() if t["slug"] == "sword_vale")
        assert item["layer_type"] == "geography"
        assert isinstance(item["tags"], list)

    def test_list_compatible_templates_by_geography(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/library/politics", params={"geography": "sword_vale"})
        assert resp.status_code == HTTPStatus.OK
        item = next(t for t in resp.json() if t["slug"] == "sword_vale")
        assert item["requires_geography"] == ["sword_vale"]

    def test_incompatible_geography_filters_out(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/library/politics", params={"geography": "nowhere"})
        assert resp.status_code == HTTPStatus.OK
        assert all(t["slug"] != "sword_vale" for t in resp.json())

    def test_unknown_layer_type_422(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        assert client.get("/api/master/library/bogus").status_code == HTTPStatus.UNPROCESSABLE_ENTITY


class TestWorldList:
    def test_custom_world_is_editable(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/worlds")
        assert resp.status_code == HTTPStatus.OK
        world = next(w for w in resp.json() if w["id"] == "test_world")
        assert world["editable"] is True
        assert world["complete"] is True

    def test_base_world_not_editable(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, content_dir = env
        _make_world(content_dir, "sword_vale")
        world = next(w for w in client.get("/api/master/worlds").json() if w["id"] == "sword_vale")
        assert world["editable"] is False


class TestCreateWorld:
    def test_create_empty(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, content_dir = env
        resp = client.post("/api/master/worlds", json={"id": "empty", "name": "Empty", "description": "d"})
        assert resp.status_code == HTTPStatus.CREATED
        assert resp.json() == {
            "id": "empty",
            "name": "Empty",
            "description": "d",
            "complete": False,
            "editable": True,
        }
        assert (content_dir / "worlds" / "empty" / "manifest.yaml").is_file()

    def test_create_duplicate_409(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post("/api/master/worlds", json={"id": "test_world", "name": "Dup"})
        assert resp.status_code == HTTPStatus.CONFLICT
        assert resp.json()["detail"] == "World 'test_world' already exists"

    def test_invalid_id_422(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post("/api/master/worlds", json={"id": "Bad Id!", "name": "X"})
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


class TestAssembleWorld:
    def test_assemble(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post(
            "/api/master/worlds/assemble",
            json={"id": "built", "name": "Built", "layer_selections": _ALL_SWORD_VALE},
        )
        assert resp.status_code == HTTPStatus.CREATED
        assert resp.json()["complete"] is True
        assert resp.json()["editable"] is True

    def test_assemble_duplicate_409(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post(
            "/api/master/worlds/assemble",
            json={"id": "test_world", "name": "Dup", "layer_selections": _ALL_SWORD_VALE},
        )
        assert resp.status_code == HTTPStatus.CONFLICT
        assert resp.json()["detail"] == "World 'test_world' already exists"

    def test_assemble_missing_layer_400(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post(
            "/api/master/worlds/assemble",
            json={"id": "partial", "name": "Partial", "layer_selections": {"geography": "sword_vale"}},
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST
        assert "Missing layer type" in resp.json()["detail"]

    def test_assemble_unknown_template_400(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        selections = {**_ALL_SWORD_VALE, "geography": "no_such_template"}
        resp = client.post(
            "/api/master/worlds/assemble",
            json={"id": "broken", "name": "Broken", "layer_selections": selections},
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST


class TestForkWorld:
    def test_fork_full(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post("/api/master/worlds/test_world/fork", json={"new_id": "copy"})
        assert resp.status_code == HTTPStatus.CREATED
        body = resp.json()
        assert body["id"] == "copy"
        assert body["name"] == "Test World"
        assert body["complete"] is True
        assert body["editable"] is True

    def test_fork_truncated_is_incomplete(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post("/api/master/worlds/test_world/fork", json={"new_id": "trunc", "from_layer": "settlements"})
        assert resp.status_code == HTTPStatus.CREATED
        assert resp.json()["complete"] is False

    def test_fork_missing_source_404(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post("/api/master/worlds/ghost/fork", json={"new_id": "copy"})
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_fork_existing_target_409(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post("/api/master/worlds/test_world/fork", json={"new_id": "test_world"})
        assert resp.status_code == HTTPStatus.CONFLICT


class TestDeleteWorld:
    def test_delete(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, content_dir = env
        resp = client.delete("/api/master/worlds/test_world")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["message"] == "World 'test_world' deleted"
        assert not (content_dir / "worlds" / "test_world").exists()

    def test_delete_base_world_403(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, content_dir = env
        _make_world(content_dir, "sword_vale")
        resp = client.delete("/api/master/worlds/sword_vale")
        assert resp.status_code == HTTPStatus.FORBIDDEN
        assert (content_dir / "worlds" / "sword_vale").exists()

    def test_delete_with_active_session_409(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, service, content_dir = env
        resp = client.post("/api/master/sessions", json={"world_name": "test_world"})
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]
        try:
            resp = client.delete("/api/master/worlds/test_world")
            assert resp.status_code == HTTPStatus.CONFLICT
            assert (content_dir / "worlds" / "test_world").exists()
        finally:
            service.delete_session(session_id)

    def test_delete_missing_404(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        assert client.delete("/api/master/worlds/ghost").status_code == HTTPStatus.NOT_FOUND


class TestWorldTemplateAndManifest:
    def test_get_template(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/worlds/test_world")
        assert resp.status_code == HTTPStatus.OK
        assert isinstance(resp.json(), dict)

    def test_get_template_missing_404(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/worlds/ghost")
        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json()["detail"] == "World 'ghost' not found"

    def test_get_manifest(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, content_dir = env
        fork_layer(content_dir, "test_world", LayerType.ENTITIES)
        resp = client.get("/api/master/worlds/test_world/manifest")
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert body["world_id"] == "test_world"
        assert body["name"] == "Test World"
        layers = {ly["layer_type"]: ly for ly in body["layers"]}
        assert set(layers) == {lt.value for lt in LayerType}
        assert layers["geography"]["source"] == "library"
        assert layers["geography"]["template"] == "sword_vale"
        assert layers["entities"]["source"] == "custom"
        assert layers["entities"]["template"] is None

    def test_get_manifest_missing_404(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/worlds/ghost/manifest")
        assert resp.status_code == HTTPStatus.NOT_FOUND
        assert resp.json()["detail"] == "World 'ghost' not found"


class TestLayerFiles:
    def test_list_files(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/worlds/test_world/layers/entities/files")
        assert resp.status_code == HTTPStatus.OK
        files = resp.json()["files"]
        assert "npcs.yaml" in files
        assert "metadata.yaml" not in files

    def test_list_files_missing_world_404(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/worlds/ghost/layers/entities/files")
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_get_file(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/worlds/test_world/layers/entities/files/npcs.yaml")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["filename"] == "npcs.yaml"
        assert len(resp.json()["content"]) > 0

    def test_get_file_bad_name_400(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/worlds/test_world/layers/entities/files/notes.txt")
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_get_file_missing_404(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.get("/api/master/worlds/test_world/layers/entities/files/nothing.yaml")
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_update_file(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, content_dir = env
        fork_layer(content_dir, "test_world", LayerType.ENTITIES)
        resp = client.put(
            "/api/master/worlds/test_world/layers/entities/files/extra.yaml", json={"content": "key: value\n"}
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["message"] == "File 'extra.yaml' updated"
        got = client.get("/api/master/worlds/test_world/layers/entities/files/extra.yaml")
        assert got.json()["content"] == "key: value\n"

    def test_update_invalid_yaml_422(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, content_dir = env
        fork_layer(content_dir, "test_world", LayerType.ENTITIES)
        resp = client.put(
            "/api/master/worlds/test_world/layers/entities/files/extra.yaml", json={"content": "a: [unclosed"}
        )
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert "YAML" in resp.json()["detail"]

    def test_update_library_layer_400(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.put("/api/master/worlds/test_world/layers/entities/files/npcs.yaml", json={"content": "a: 1"})
        assert resp.status_code == HTTPStatus.BAD_REQUEST
        assert "fork it first" in resp.json()["detail"]

    def test_update_bad_filename_400(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, content_dir = env
        fork_layer(content_dir, "test_world", LayerType.ENTITIES)
        resp = client.put("/api/master/worlds/test_world/layers/entities/files/.hidden.yaml", json={"content": "a"})
        assert resp.status_code == HTTPStatus.BAD_REQUEST


class TestScaffoldAndForkLayer:
    def test_scaffold(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        client.post("/api/master/worlds", json={"id": "empty", "name": "Empty"})
        resp = client.post("/api/master/worlds/empty/layers/geography/scaffold")
        assert resp.status_code == HTTPStatus.CREATED
        assert resp.json()["message"] == "Layer 'geography' scaffolded in world 'empty'"

    def test_scaffold_already_defined_409(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post("/api/master/worlds/test_world/layers/geography/scaffold")
        assert resp.status_code == HTTPStatus.CONFLICT
        assert "already defined" in resp.json()["detail"]

    def test_scaffold_missing_world_404(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        assert client.post("/api/master/worlds/ghost/layers/geography/scaffold").status_code == HTTPStatus.NOT_FOUND

    def test_fork_layer(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        resp = client.post("/api/master/worlds/test_world/fork/entities")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["message"] == "Layer 'entities' forked to custom in world 'test_world'"
        manifest = client.get("/api/master/worlds/test_world/manifest").json()
        entities = next(ly for ly in manifest["layers"] if ly["layer_type"] == "entities")
        assert entities["source"] == "custom"

    def test_fork_layer_twice_409(self, env: tuple[TestClient, GameService, Path]) -> None:
        client, _service, _dir = env
        client.post("/api/master/worlds/test_world/fork/entities")
        resp = client.post("/api/master/worlds/test_world/fork/entities")
        assert resp.status_code == HTTPStatus.CONFLICT
        assert "already custom" in resp.json()["detail"]
