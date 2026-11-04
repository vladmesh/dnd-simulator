"""HTTP coverage for player setup, domain errors, and level-up responses."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
from test_api import _DEFAULT_SCORES, _create_session, _create_session_with_player, _make_client
from test_api_deps import _restore_state as _restore_state


@pytest.fixture(autouse=True)
def _seed_rngs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DND_WORLD_SEED", "42")
    monkeypatch.setenv("DND_DICE_SEED", "42")


def test_setup_config_exposes_character_creation_limits(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)

    response = client.get("/api/player/setup-config")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"starting_gold": 1000, "point_buy_budget": 27}


@pytest.mark.parametrize(
    ("endpoint", "method", "body"),
    [
        ("character", "POST", {"name": "Tester", "ability_scores": _DEFAULT_SCORES}),
        ("status", "GET", None),
        ("level-up", "POST", {}),
    ],
)
def test_unknown_session_returns_domain_error(
    tmp_path: Path, endpoint: str, method: str, body: dict[str, object] | None
) -> None:
    client, _ = _make_client(tmp_path)

    response = client.request(method, f"/api/player/sessions/missing/{endpoint}", json=body)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Session 'missing' not found"}


@pytest.mark.parametrize(("endpoint", "method"), [("status", "GET"), ("level-up", "POST")])
def test_session_without_player_returns_domain_error(tmp_path: Path, endpoint: str, method: str) -> None:
    client, _ = _make_client(tmp_path)
    sid = _create_session(client)

    response = client.request(method, f"/api/player/sessions/{sid}/{endpoint}", json={} if method == "POST" else None)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "No player in this session"}


def test_invalid_character_class_does_not_create_player(tmp_path: Path) -> None:
    client, service = _make_client(tmp_path)
    sid = _create_session(client)

    response = client.post(
        f"/api/player/sessions/{sid}/character",
        json={"name": "Tester", "char_class": "not_a_class", "ability_scores": _DEFAULT_SCORES},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {"detail": "Unknown class: not_a_class"}
    assert service.get_session(sid).get_player() is None


@pytest.mark.parametrize(
    ("style", "detail"),
    [(None, "No level-up available"), ("not_a_style", "'not_a_style' is not a valid FightingStyle")],
)
def test_rejected_level_up_leaves_player_unchanged(tmp_path: Path, style: str | None, detail: str) -> None:
    client, _ = _make_client(tmp_path)
    sid = _create_session_with_player(client)
    before = client.get(f"/api/player/sessions/{sid}/status")
    assert before.status_code == HTTPStatus.OK

    response = client.post(
        f"/api/player/sessions/{sid}/level-up", json={} if style is None else {"fighting_style": style}
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {"detail": detail}
    after = client.get(f"/api/player/sessions/{sid}/status")
    assert after.status_code == HTTPStatus.OK
    assert after.json() == before.json()


@pytest.mark.parametrize(("char_class", "style"), [("fighter", None), ("paladin", "defense")])
def test_level_up_returns_updated_player_status(tmp_path: Path, char_class: str, style: str | None) -> None:
    client, service = _make_client(tmp_path)
    sid = _create_session(client)
    created = client.post(
        f"/api/player/sessions/{sid}/character",
        json={"name": "Tester", "char_class": char_class, "ability_scores": _DEFAULT_SCORES},
    )
    assert created.status_code == HTTPStatus.OK
    assert created.json()["level"] == 1
    assert created.json()["max_hp"] == 12
    player = service.get_session(sid).get_player(created.json()["player_id"])
    assert player is not None
    player.experience = 300
    player.level_up_available = True
    player.current_hp = 5

    response = client.post(
        f"/api/player/sessions/{sid}/level-up", json={} if style is None else {"fighting_style": style}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["player_id"] == created.json()["player_id"]
    assert data["char_class"] == char_class
    assert data["level"] == 2
    assert data["max_hp"] == 20
    assert data["hp"] == 13
    assert data["experience"] == 300
    assert data["level_up_available"] is False
    assert player.level == 2
    assert player.level_up_available is False
    status = client.get(f"/api/player/sessions/{sid}/status")
    assert status.status_code == HTTPStatus.OK
    assert status.json() == data
