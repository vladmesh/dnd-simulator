from __future__ import annotations

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _make_client(tmp_path: object) -> tuple[TestClient, GameService]:
    from pathlib import Path

    store = JsonFileStore(Path(str(tmp_path)) / "saves")
    service = GameService(store=store)
    set_service(service)
    return TestClient(app), service


class TestHealthEndpoint:
    def test_health(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestMasterEndpoints:
    def test_create_session(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={"world_file": "test_world.yaml"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["player_name"] != ""
        assert data["player_location"] != ""

    def test_get_session_state(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={})
        session_id = resp.json()["session_id"]

        resp = client.get(f"/api/master/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["regions"]) > 0
        assert len(data["entities"]) > 0

    def test_get_nonexistent_session(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.get("/api/master/sessions/doesnotexist")
        assert resp.status_code == 404


class TestPlayerEndpoints:
    def test_get_status(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={})
        session_id = resp.json()["session_id"]

        resp = client.get(f"/api/player/sessions/{session_id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] != ""
        assert data["hp"] > 0
        assert "str" in data["ability_scores"]

    def test_player_action_look(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={})
        session_id = resp.json()["session_id"]

        resp = client.post(f"/api/player/sessions/{session_id}/action", json={"action": "look"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["text"]) > 0

    def test_player_action_status(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={})
        session_id = resp.json()["session_id"]

        resp = client.post(f"/api/player/sessions/{session_id}/action", json={"action": "status"})
        assert resp.status_code == 200
        assert "HP" in resp.json()["text"]

    def test_player_action_nonexistent_session(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/player/sessions/nope/action", json={"action": "look"})
        assert resp.status_code == 404
