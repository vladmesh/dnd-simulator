"""WebSocket regression for malformed actions reaching the live round thread."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _receive_turn(ws: object) -> dict[str, object]:
    while True:
        message = ws.receive_json()  # type: ignore[attr-defined]
        if message["type"] == "turn":
            return message
        assert message["type"] == "round_result"


def test_missing_travel_destination_keeps_ws_round_alive(tmp_path: Path) -> None:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    set_service(service)
    client = TestClient(app)

    response = client.post("/api/master/sessions", json={})
    assert response.status_code == HTTPStatus.OK
    session_id = response.json()["session_id"]
    response = client.post(
        f"/api/player/sessions/{session_id}/character",
        json={
            "name": "Traveler",
            "race": "human",
            "char_class": "fighter",
            "ability_scores": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
        },
    )
    assert response.status_code == HTTPStatus.OK

    with client.websocket_connect(f"/api/ws/{session_id}") as ws:
        _receive_turn(ws)
        ws.send_json({"type": "action", "name": "travel", "params": {}})

        failed = ws.receive_json()
        assert failed["type"] == "action_result"
        assert failed["action"] == "travel"
        assert failed["error"]

        next_message = ws.receive_json()
        if next_message["type"] == "round_result":
            next_message = ws.receive_json()
        assert next_message["type"] == "turn"

        ws.send_json({"type": "action", "name": "say", "params": {"text": "Still here"}})
        succeeded = ws.receive_json()
        assert succeeded["type"] == "action_result"
        assert succeeded["action"] == "say"
        assert "error" not in succeeded


def test_live_action_failure_uses_current_session_language(tmp_path: Path) -> None:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    set_service(service)
    client = TestClient(app)

    response = client.post("/api/master/sessions", json={"lang": "en"})
    assert response.status_code == HTTPStatus.OK
    session_id = response.json()["session_id"]
    response = client.post(
        f"/api/player/sessions/{session_id}/character",
        json={
            "name": "Traveler",
            "race": "human",
            "char_class": "fighter",
            "ability_scores": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
        },
    )
    assert response.status_code == HTTPStatus.OK

    with client.websocket_connect(f"/api/ws/{session_id}") as ws:
        _receive_turn(ws)

        ws.send_json({"type": "action", "name": "attack", "params": {}})
        failed = ws.receive_json()
        assert failed["type"] == "action_result"
        assert failed["error"] == "Action 'attack' requires parameter 'target_id'"
        _receive_turn(ws)

        response = client.put(f"/api/master/sessions/{session_id}/lang", json={"lang": "ru"})
        assert response.status_code == HTTPStatus.OK

        ws.send_json({"type": "action", "name": "attack", "params": {}})
        failed = ws.receive_json()
        assert failed["type"] == "action_result"
        assert failed["error"] == "Для действия 'attack' нужен параметр 'target_id'"
        _receive_turn(ws)

        ws.send_json({"type": "action", "name": "say", "params": {"text": "Still here"}})
        succeeded = ws.receive_json()
        assert succeeded["type"] == "action_result"
        assert succeeded["action"] == "say"
        assert "error" not in succeeded
