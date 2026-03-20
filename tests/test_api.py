from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _make_client(tmp_path: object) -> tuple[TestClient, GameService]:
    store = JsonFileStore(Path(str(tmp_path)) / "saves")
    service = GameService(store=store)
    set_service(service)
    return TestClient(app), service


def _create_session(client: TestClient) -> str:
    resp = client.post("/api/master/sessions", json={})
    assert resp.status_code == 200
    return resp.json()["session_id"]


class TestHealthEndpoint:
    def test_health(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestWorldsEndpoint:
    def test_list_worlds(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds")
        assert resp.status_code == 200
        worlds = resp.json()
        assert len(worlds) >= 1
        assert any(w["id"] == "sword_vale" for w in worlds)


class TestMasterSessions:
    def test_create_session(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={"world_name": "test_world.yaml"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["player_name"] != ""

    def test_create_session_directory_format(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={"world_name": "sword_vale"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        # sword_vale has no player.yaml, so player_name should be empty
        assert data["player_name"] == ""

    def test_get_session_state(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/master/sessions/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["regions"]) > 0
        assert len(data["entities"]) > 0

    def test_delete_session(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.delete(f"/api/master/sessions/{sid}")
        assert resp.status_code == 200
        # Session should be gone
        resp = client.get(f"/api/master/sessions/{sid}")
        assert resp.status_code == 404

    def test_get_nonexistent_session(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.get("/api/master/sessions/doesnotexist")
        assert resp.status_code == 404


class TestNpcHotControls:
    def test_list_npcs(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/master/sessions/{sid}/npcs")
        assert resp.status_code == 200
        npcs = resp.json()
        assert len(npcs) >= 3
        assert any(n["id"] == "edgar" for n in npcs)

    def test_get_npc(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/master/sessions/{sid}/npcs/edgar")
        assert resp.status_code == 200
        npc = resp.json()
        assert npc["name"] == "Edgar the Smith"
        assert npc["role"] == "blacksmith"

    def test_spawn_npc(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/master/sessions/{sid}/npcs",
            json={
                "id": "goblin_scout",
                "name": "Goblin Scout",
                "region_id": "silverport",
                "role": "guard",
                "hp": 7,
                "ac": 13,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == "goblin_scout"

        # Verify it shows up in list
        resp = client.get(f"/api/master/sessions/{sid}/npcs/goblin_scout")
        assert resp.status_code == 200

    def test_patch_npc(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.patch(
            f"/api/master/sessions/{sid}/npcs/edgar",
            json={"current_hp": 5, "personality": "Now angry"},
        )
        assert resp.status_code == 200

        resp = client.get(f"/api/master/sessions/{sid}/npcs/edgar")
        npc = resp.json()
        assert npc["hp"] == 5
        assert "angry" in npc["personality"].lower()

    def test_delete_npc(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.delete(f"/api/master/sessions/{sid}/npcs/edgar")
        assert resp.status_code == 200

        resp = client.get(f"/api/master/sessions/{sid}/npcs/edgar")
        assert resp.status_code == 404

    def test_set_brain_rule_based(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.put(
            f"/api/master/sessions/{sid}/npcs/edgar/brain",
            json={"type": "rule_based"},
        )
        assert resp.status_code == 200

    def test_set_brain_llm_no_config(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.put(
            f"/api/master/sessions/{sid}/npcs/edgar/brain",
            json={"type": "llm"},
        )
        assert resp.status_code == 400  # LLM not configured


class TestNationSettlementHotControls:
    def test_patch_nation(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.patch(
            f"/api/master/sessions/{sid}/nations/silverhold",
            json={"wealth": 100.0, "military": 80.0},
        )
        assert resp.status_code == 200

    def test_patch_nation_not_found(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.patch(
            f"/api/master/sessions/{sid}/nations/nonexistent",
            json={"wealth": 100.0},
        )
        assert resp.status_code == 404

    def test_patch_settlement(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.patch(
            f"/api/master/sessions/{sid}/settlements/silverport_city",
            json={"population": 10000},
        )
        assert resp.status_code == 200


class TestTimeControl:
    def test_advance_time(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/master/sessions/{sid}/time/advance",
            json={"hours": 6},
        )
        assert resp.status_code == 200
        assert "Advanced 6h" in resp.json()["message"]


class TestPlayerEndpoints:
    def test_get_status(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/player/sessions/{sid}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] != ""
        assert data["hp"] > 0
        assert "str" in data["ability_scores"]

    def test_player_action_look(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(f"/api/player/sessions/{sid}/action", json={"action": "look"})
        assert resp.status_code == 200
        assert len(resp.json()["text"]) > 0

    def test_player_action_nonexistent_session(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/player/sessions/nope/action", json={"action": "look"})
        assert resp.status_code == 404
