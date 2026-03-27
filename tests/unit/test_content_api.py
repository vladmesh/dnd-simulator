"""Tests for entity CRUD API endpoints — world entities and catalog entries via REST."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.content_loader.assembly import assemble_world, fork_layer
from dnd_simulator.content_loader.manifest import LayerType
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / "content"


def _with_library(tmp_path: Path) -> Path:
    """Create a content dir that symlinks the real library and catalogs."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "worlds").mkdir()
    (content_dir / "library").symlink_to(CONTENT_DIR / "library")
    catalogs_src = CONTENT_DIR / "catalogs"
    if catalogs_src.exists():
        (content_dir / "catalogs").symlink_to(catalogs_src)
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


def _make_client(tmp_path: Path) -> tuple[TestClient, GameService, Path]:
    """Create a TestClient with isolated content dir."""
    content_dir = _with_library(tmp_path)
    _make_world(content_dir)
    # Fork the entities layer so it's writable
    fork_layer(content_dir, "test_world", LayerType.ENTITIES)
    service = GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=content_dir)
    set_service(service)
    return TestClient(app), service, content_dir


def _npc_data(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": {"en": "Test NPC"},
        "race": "human",
        "class": "commoner",
        "role": "commoner",
        "start_location": "silverport_city_tavern",
        "hp": 10,
        "ac": 10,
    }
    base.update(overrides)
    return base


def _monster_catalog_data(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": {"en": "Test Beast"},
        "hp": 20,
        "ac": 13,
        "speed": 40,
        "cr": 1.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# World entity CRUD
# ---------------------------------------------------------------------------


class TestCreateAndGetEntity:
    """Create NPC via API, read it back."""

    def test_create_and_get(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        data = _npc_data()

        resp = client.post("/api/master/worlds/test_world/entities/npc/new_npc", json=data)
        assert resp.status_code == HTTPStatus.CREATED
        body = resp.json()
        assert body["id"] == "new_npc"
        assert body["data"]["name"] == {"en": "Test NPC"}

        resp = client.get("/api/master/worlds/test_world/entities/npc/new_npc")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"]["hp"] == 10


class TestListEntities:
    """Create 2 NPCs, list them, confirm both present."""

    def test_list(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        client.post(
            "/api/master/worlds/test_world/entities/npc/npc_a",
            json=_npc_data(name={"en": "A"}),
        )
        client.post(
            "/api/master/worlds/test_world/entities/npc/npc_b",
            json=_npc_data(name={"en": "B"}),
        )

        resp = client.get("/api/master/worlds/test_world/entities/npc")
        assert resp.status_code == HTTPStatus.OK
        items = resp.json()
        ids = [item["id"] for item in items]
        assert "npc_a" in ids
        assert "npc_b" in ids


class TestUpdateEntity:
    """Create NPC, PUT with changed HP, confirm."""

    def test_update(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        client.post(
            "/api/master/worlds/test_world/entities/npc/upd_npc",
            json=_npc_data(hp=10),
        )

        resp = client.put(
            "/api/master/worlds/test_world/entities/npc/upd_npc",
            json=_npc_data(hp=99),
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"]["hp"] == 99

        resp = client.get("/api/master/worlds/test_world/entities/npc/upd_npc")
        assert resp.json()["data"]["hp"] == 99


class TestDeleteEntity:
    """Create NPC, DELETE, confirm 404."""

    def test_delete(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        client.post(
            "/api/master/worlds/test_world/entities/npc/del_npc",
            json=_npc_data(),
        )

        resp = client.delete("/api/master/worlds/test_world/entities/npc/del_npc")
        assert resp.status_code == HTTPStatus.OK

        resp = client.get("/api/master/worlds/test_world/entities/npc/del_npc")
        assert resp.status_code == HTTPStatus.NOT_FOUND


class TestLibraryLayerRejectsWrites:
    """POST/PUT/DELETE on a library-backed layer returns 400."""

    def test_create_on_library_rejects(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        # Geography is still library-backed (not forked)
        resp = client.post(
            "/api/master/worlds/test_world/entities/region/new_region",
            json={"name": {"en": "X"}, "latitude": 0, "longitude": 0, "elevation": 0, "terrain": "PLAIN"},
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST
        assert "library" in resp.json()["detail"].lower() or "fork" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Catalog CRUD
# ---------------------------------------------------------------------------


class TestCatalogCrudRoundTrip:
    """POST → GET → PUT → DELETE for catalog entries."""

    def test_monster_catalog_crud(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)

        # Create
        resp = client.post(
            "/api/master/catalogs/monster_catalog/test_beast",
            json=_monster_catalog_data(),
        )
        assert resp.status_code == HTTPStatus.CREATED
        assert resp.json()["id"] == "test_beast"

        # Read
        resp = client.get("/api/master/catalogs/monster_catalog/test_beast")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"]["hp"] == 20

        # Update
        resp = client.put(
            "/api/master/catalogs/monster_catalog/test_beast",
            json=_monster_catalog_data(hp=50),
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"]["hp"] == 50

        # Delete
        resp = client.delete("/api/master/catalogs/monster_catalog/test_beast")
        assert resp.status_code == HTTPStatus.OK

        resp = client.get("/api/master/catalogs/monster_catalog/test_beast")
        assert resp.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Validation & error handling
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """Invalid data returns 422."""

    def test_invalid_race(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.post(
            "/api/master/worlds/test_world/entities/npc/bad_npc",
            json={"name": {"en": "Bad"}, "race": "not_a_real_race"},
        )
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


class TestNotFound:
    """404 on missing entities and worlds."""

    def test_get_nonexistent_entity(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds/test_world/entities/npc/ghost")
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_get_from_nonexistent_world(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds/no_such_world/entities/npc")
        assert resp.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Schema endpoints
# ---------------------------------------------------------------------------


class TestSchemaEndpoint:
    """GET /schemas/{entity_type} returns valid JSON Schema."""

    def test_npc_schema_returns_json_schema(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/schemas/npc")
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert body["type"] == "object"
        assert "properties" in body
        assert "required" in body or "properties" in body  # valid schema structure

    def test_unknown_entity_type_422(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/schemas/not_real")
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_schema_list(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/schemas")
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert isinstance(body, list)
        type_names = {s["entity_type"] for s in body}
        assert "npc" in type_names
        assert "region" in type_names


# ---------------------------------------------------------------------------
# Refs endpoints
# ---------------------------------------------------------------------------


class TestRefsEndpoint:
    """GET /worlds/{world_id}/refs/{ref_type} returns ID+name pairs."""

    def test_refs_locations(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds/test_world/refs/locations")
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0
        first = body[0]
        assert "id" in first
        assert "name" in first

    def test_refs_settlements(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds/test_world/refs/settlements")
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0

    def test_refs_regions(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds/test_world/refs/regions")
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0

    def test_refs_nations(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds/test_world/refs/nations")
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0

    def test_refs_unknown_type_422(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds/test_world/refs/not_real")
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_refs_nonexistent_world_404(self, tmp_path: Path) -> None:
        client, _, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds/ghost_world/refs/locations")
        assert resp.status_code == HTTPStatus.NOT_FOUND
