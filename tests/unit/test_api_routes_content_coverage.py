"""Exercise content-route error responses against real, isolated content storage."""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import _make_client

from dnd_simulator.adapters.api import deps


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(deps, "_service", deps._service)
    api_client, _ = _make_client(tmp_path, isolated_content=True)
    catalogs = tmp_path / "content" / "catalogs"
    if catalogs.is_symlink():
        catalogs.unlink()
    catalogs.mkdir(exist_ok=True)
    try:
        yield api_client
    finally:
        api_client.close()


@pytest.fixture
def location_url(client: TestClient) -> str:
    response = client.post("/api/master/worlds/sword_vale/fork", json={"new_id": "coverage_world"})
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["id"] == "coverage_world"
    response = client.post("/api/master/worlds/coverage_world/fork/geography")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"message": "Layer 'geography' forked to custom in world 'coverage_world'"}
    url = "/api/master/worlds/coverage_world/entities/location/coverage_location"
    response = client.post(url, json={"name": {"en": "Original location"}, "region": "silverport"})
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["id"] == "coverage_location"
    assert response.json()["data"]["name"] == {"en": "Original location"}
    return url


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ({"name": "Invalid location"}, "Field required"),
        ({"name": "Invalid location", "region": 42}, "Input should be a valid string"),
    ],
)
def test_invalid_entity_update_preserves_original(
    client: TestClient, location_url: str, body: dict[str, object], error: str
) -> None:
    before = client.get(location_url)
    assert before.status_code == HTTPStatus.OK

    response = client.put(location_url, json=body)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    detail = response.json()["detail"]
    assert "LocationContent" in detail
    assert "region" in detail
    assert error in detail
    after = client.get(location_url)
    assert after.status_code == HTTPStatus.OK
    assert after.json() == before.json()


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_library_entity_writes_are_rejected(client: TestClient, method: str) -> None:
    url = "/api/master/worlds/sword_vale/entities/location/silverport_city_gate"
    before = client.get(url)
    assert before.status_code == HTTPStatus.OK

    response = client.request(method, url, json={"name": "Changed location", "region": "silverport"})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {"detail": "Cannot write to library layer — fork it first"}
    after = client.get(url)
    assert after.status_code == HTTPStatus.OK
    assert after.json() == before.json()


@pytest.mark.parametrize(
    ("catalog_type", "body", "schema", "field", "error"),
    [
        ("monster_catalog", {"name": "Incomplete monster"}, "MonsterTemplateContent", "hp", "Field required"),
        (
            "item_catalog",
            {"name": "Invalid item", "type": "not_an_item_type"},
            "ItemContent",
            "type",
            "Input should be",
        ),
    ],
)
def test_invalid_catalog_creation_leaves_catalog_empty(
    client: TestClient, catalog_type: str, body: dict[str, object], schema: str, field: str, error: str
) -> None:
    url = f"/api/master/catalogs/{catalog_type}"

    response = client.post(f"{url}/invalid_entry", json=body)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    detail = response.json()["detail"]
    assert schema in detail
    assert field in detail
    assert error in detail
    entries = client.get(url)
    assert entries.status_code == HTTPStatus.OK
    assert entries.json() == []
    missing = client.get(f"{url}/invalid_entry")
    assert missing.status_code == HTTPStatus.NOT_FOUND
    assert f"{catalog_type} 'invalid_entry' not found" in missing.json()["detail"]


@pytest.mark.parametrize(
    ("catalog_type", "body"),
    [
        ("monster_catalog", {"name": {"en": "Coverage beast"}, "hp": 7, "ac": 12, "speed": 30, "cr": 0.25}),
        ("item_catalog", {"name": "Coverage blade", "type": "weapon", "price": 5}),
    ],
)
def test_duplicate_catalog_creation_preserves_listed_entry(
    client: TestClient, catalog_type: str, body: dict[str, object]
) -> None:
    url = f"/api/master/catalogs/{catalog_type}"
    created = client.post(f"{url}/coverage_entry", json=body)
    assert created.status_code == HTTPStatus.CREATED
    assert created.json()["id"] == "coverage_entry"
    for field, value in body.items():
        assert created.json()["data"][field] == value

    response = client.post(f"{url}/coverage_entry", json={**body, "name": "Replacement"})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert f"{catalog_type} 'coverage_entry' already exists" in response.json()["detail"]
    stored = client.get(f"{url}/coverage_entry")
    assert stored.status_code == HTTPStatus.OK
    assert stored.json() == created.json()
    entries = client.get(url)
    assert entries.status_code == HTTPStatus.OK
    assert entries.json() == [created.json()]
