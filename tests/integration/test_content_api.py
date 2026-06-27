"""Content CRUD API integration tests.

Tests run against a live backend in docker compose.
CRUD tests fork arena into a throwaway world to avoid mutating shared fixtures.
Library write-rejection assembles a throwaway library-backed world at runtime.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from http import HTTPStatus

import pytest
import requests

# ---------------------------------------------------------------------------
# Schema endpoints (read-only, no world needed)
# ---------------------------------------------------------------------------


class TestSchemaList:
    def test_list_returns_all_types(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/schemas", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        types = {s["entity_type"] for s in body}
        assert "npc" in types
        assert "region" in types
        assert "monster_catalog" in types
        assert "item_catalog" in types


class TestSchemaDetail:
    def test_npc_schema(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/schemas/npc", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert body["type"] == "object"
        assert "properties" in body
        # Must have key NPC fields
        props = body["properties"]
        assert "name" in props
        assert "race" in props
        assert "hp" in props

    def test_npc_schema_has_x_ref_type(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/schemas/npc", timeout=5)
        body = resp.json()
        props = body["properties"]
        assert props["start_location"].get("x-ref-type") == "locations"

    def test_unknown_type_422(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/schemas/nonexistent", timeout=5)
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# Refs endpoints (read-only, need a world)
# ---------------------------------------------------------------------------


class TestRefs:
    def test_locations(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/worlds/arena/refs/locations", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0
        assert "id" in body[0]
        assert "name" in body[0]

    def test_regions(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/worlds/arena/refs/regions", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        assert len(resp.json()) > 0

    def test_unknown_ref_type_422(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/worlds/arena/refs/bogus", timeout=5)
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_nonexistent_world_404(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/worlds/no_such_world/refs/locations", timeout=5)
        assert resp.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Entity CRUD — fork arena into a throwaway world so we don't mutate fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def crud_world(api_url: str) -> Iterator[str]:
    """Fork arena into a disposable world for CRUD tests, delete on teardown."""
    resp = requests.post(
        f"{api_url}/worlds/arena/fork",
        json={"new_id": "crud_integ_test"},
        timeout=10,
    )
    resp.raise_for_status()
    yield "crud_integ_test"
    requests.delete(f"{api_url}/worlds/crud_integ_test", timeout=5)


class TestEntityCrud:
    """Full CRUD cycle on a forked world's entities layer."""

    def test_list_npcs(self, api_url: str, crud_world: str) -> None:
        resp = requests.get(f"{api_url}/worlds/{crud_world}/entities/npc", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        items = resp.json()
        ids = [item["id"] for item in items]
        assert "razor" in ids  # inherited from arena

    def test_create_read_update_delete(self, api_url: str, crud_world: str) -> None:
        base_url = f"{api_url}/worlds/{crud_world}/entities/npc/integ_test_npc"

        # Create
        npc_data = {
            "name": "Integration Test NPC",
            "race": "human",
            "class": "commoner",
            "role": "commoner",
            "start_location": "arena_floor",
            "hp": 5,
            "ac": 10,
        }
        resp = requests.post(base_url, json=npc_data, timeout=5)
        assert resp.status_code == HTTPStatus.CREATED
        body = resp.json()
        assert body["id"] == "integ_test_npc"
        assert body["data"]["hp"] == 5

        # Read
        resp = requests.get(base_url, timeout=5)
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"]["hp"] == 5

        # Update
        npc_data["hp"] = 99
        resp = requests.put(base_url, json=npc_data, timeout=5)
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["data"]["hp"] == 99

        # Confirm update persisted
        resp = requests.get(base_url, timeout=5)
        assert resp.json()["data"]["hp"] == 99

        # Delete
        resp = requests.delete(base_url, timeout=5)
        assert resp.status_code == HTTPStatus.OK

        # Confirm gone
        resp = requests.get(base_url, timeout=5)
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_get_nonexistent_entity_404(self, api_url: str, crud_world: str) -> None:
        resp = requests.get(f"{api_url}/worlds/{crud_world}/entities/npc/ghost_npc", timeout=5)
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_validation_error_422(self, api_url: str, crud_world: str) -> None:
        resp = requests.post(
            f"{api_url}/worlds/{crud_world}/entities/npc/bad_npc",
            json={"name": "Bad", "race": "not_a_race"},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# Library layer rejects writes
# ---------------------------------------------------------------------------


class TestLibraryRejectsWrites:
    """Write operations on library-backed layers return 400."""

    def test_create_on_library_layer_rejected(self, api_url: str) -> None:
        # Assemble a throwaway world whose layers are all library-backed,
        # then verify entity writes are rejected (caller must fork first).
        world_id = f"asm_libwrite_{uuid.uuid4().hex[:8]}"
        assembled = requests.post(
            f"{api_url}/worlds/assemble",
            json={
                "id": world_id,
                "name": "Lib Write Test",
                "layer_selections": {
                    "geography": "test_geo",
                    "politics": "test_pol",
                    "settlements": "test_set",
                    "ecology": "test_eco",
                    "entities": "test_ent",
                },
            },
            timeout=10,
        )
        assembled.raise_for_status()
        try:
            resp = requests.post(
                f"{api_url}/worlds/{world_id}/entities/npc/blocked_npc",
                json={
                    "name": "Blocked",
                    "race": "human",
                    "class": "commoner",
                    "role": "commoner",
                    "start_location": "test_loc",
                    "hp": 5,
                    "ac": 10,
                },
                timeout=5,
            )
            assert resp.status_code == HTTPStatus.BAD_REQUEST
            detail = resp.json()["detail"].lower()
            assert "library" in detail or "fork" in detail
        finally:
            requests.delete(f"{api_url}/worlds/{world_id}", timeout=5)


# ---------------------------------------------------------------------------
# Catalog CRUD
# ---------------------------------------------------------------------------


class TestCatalogCrud:
    """CRUD on monster catalog (global, not per-world)."""

    def test_list_monsters(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/catalogs/monster_catalog", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        items = resp.json()
        ids = [item["id"] for item in items]
        assert "goblin" in ids  # known catalog entry

    def test_create_read_update_delete(self, api_url: str) -> None:
        base_url = f"{api_url}/catalogs/monster_catalog/integ_test_beast"

        monster_data = {
            "name": "Integration Beast",
            "hp": 25,
            "ac": 14,
            "speed": 30,
            "cr": 2.0,
        }

        try:
            # Create
            resp = requests.post(base_url, json=monster_data, timeout=5)
            assert resp.status_code == HTTPStatus.CREATED
            assert resp.json()["id"] == "integ_test_beast"

            # Read
            resp = requests.get(base_url, timeout=5)
            assert resp.status_code == HTTPStatus.OK
            assert resp.json()["data"]["hp"] == 25

            # Update
            monster_data["hp"] = 50
            resp = requests.put(base_url, json=monster_data, timeout=5)
            assert resp.status_code == HTTPStatus.OK
            assert resp.json()["data"]["hp"] == 50

            # Delete
            resp = requests.delete(base_url, timeout=5)
            assert resp.status_code == HTTPStatus.OK

            # Confirm gone
            resp = requests.get(base_url, timeout=5)
            assert resp.status_code == HTTPStatus.NOT_FOUND
        finally:
            # Ensure cleanup even if assertions fail mid-test
            requests.delete(base_url, timeout=5)

    def test_get_nonexistent_catalog_404(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/catalogs/monster_catalog/no_such_beast", timeout=5)
        assert resp.status_code == HTTPStatus.NOT_FOUND
