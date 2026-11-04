from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import _create_session, _make_client

from dnd_simulator.service import GameService


@pytest.fixture
def api(tmp_path: Path) -> tuple[TestClient, GameService]:
    return _make_client(tmp_path)


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("DELETE", "", None),
        ("PATCH", "/nations/silverhold", {"wealth": 50.0}),
        ("PATCH", "/settlements/silverport_city", {"population": 100}),
        ("POST", "/time/advance", {"hours": 1}),
        ("POST", "/save", None),
        ("POST", "/saves/checkpoint/load", None),
        ("DELETE", "/saves/checkpoint", None),
    ],
)
def test_missing_session_returns_404(
    api: tuple[TestClient, GameService], method: str, suffix: str, body: dict[str, object] | None
) -> None:
    client, _ = api

    response = client.request(method, f"/api/master/sessions/missing{suffix}", json=body)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Session 'missing' not found"}


@pytest.mark.parametrize(
    ("resource", "field"),
    [
        ("creatures/edgar", "current_hp"),
        ("nations/silverhold", "wealth"),
        ("settlements/silverport_city", "population"),
    ],
)
@pytest.mark.parametrize("explicit_null", [False, True])
def test_empty_patch_rejected_without_changing_world(
    api: tuple[TestClient, GameService], resource: str, field: str, explicit_null: bool
) -> None:
    client, _ = api
    sid = _create_session(client)
    url = f"/api/master/sessions/{sid}"
    before = client.get(url)
    assert before.status_code == HTTPStatus.OK

    response = client.patch(f"{url}/{resource}", json={field: None} if explicit_null else {})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {"detail": "No fields to update"}
    after = client.get(url)
    assert after.status_code == HTTPStatus.OK
    assert after.json() == before.json()


def test_give_item_to_missing_creature_returns_400(api: tuple[TestClient, GameService]) -> None:
    client, _ = api
    sid = _create_session(client)

    response = client.post(
        f"/api/master/sessions/{sid}/creatures/missing/items",
        json={"name": "Healing potion", "type": "potion", "heal_dice": "1d4"},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {"detail": "Creature 'missing' not found"}


def test_delete_save_removes_file_and_listing(api: tuple[TestClient, GameService], tmp_path: Path) -> None:
    client, service = api
    sid = _create_session(client)
    service.get_session(sid).dice_rng.seed(0)
    url = f"/api/master/sessions/{sid}"

    saved = client.post(f"{url}/save", params={"name": "checkpoint"})
    assert saved.status_code == HTTPStatus.OK
    assert saved.json() == {"message": "Saved as 'checkpoint'"}
    save_path = tmp_path / "saves" / "sword_vale" / "checkpoint.json"
    assert save_path.is_file()
    before = client.get(f"{url}/saves")
    assert before.status_code == HTTPStatus.OK
    assert before.json() == {"saves": ["checkpoint"]}

    response = client.delete(f"{url}/saves/checkpoint")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"message": "Deleted 'checkpoint'"}
    assert not save_path.exists()
    after = client.get(f"{url}/saves")
    assert after.status_code == HTTPStatus.OK
    assert after.json() == {"saves": []}
    state = client.get(url)
    assert state.status_code == HTTPStatus.OK
    assert state.json()["entities"]
