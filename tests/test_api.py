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


class TestPlayerCharacterCreation:
    def _create_session_no_player(self, client: TestClient) -> str:
        resp = client.post("/api/master/sessions", json={"world_name": "sword_vale"})
        assert resp.status_code == 200
        return resp.json()["session_id"]

    def test_create_character(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = self._create_session_no_player(client)

        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Thrain",
                "race": "dwarf",
                "char_class": "fighter",
                "hp": 14,
                "ac": 16,
                "gold": 100,
                "start_region": "silverport",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Thrain"
        assert data["race"] == "dwarf"
        assert data["hp"] == 14
        assert data["location_id"] == "silverport"

    def test_create_character_default_region(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = self._create_session_no_player(client)

        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={"name": "Nobody"},
        )
        assert resp.status_code == 200
        assert resp.json()["location_id"] != ""

    def test_create_character_twice_fails(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = self._create_session_no_player(client)

        client.post(f"/api/player/sessions/{sid}/character", json={"name": "First"})
        resp = client.post(f"/api/player/sessions/{sid}/character", json={"name": "Second"})
        assert resp.status_code == 400

    def test_status_without_player(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = self._create_session_no_player(client)

        resp = client.get(f"/api/player/sessions/{sid}/status")
        assert resp.status_code == 404


class TestPlayerPerception:
    def test_get_perception(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.get(f"/api/player/sessions/{sid}/perception")
        assert resp.status_code == 200
        data = resp.json()
        assert "weather" in data
        assert "location" in data
        assert "entities" in data
        assert "neighbors" in data
        assert "time" in data

    def test_perception_entities_are_perceived(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.get(f"/api/player/sessions/{sid}/perception")
        data = resp.json()
        # Entities should have description (from perceive), not raw stats
        for e in data["entities"]:
            assert "id" in e
            assert "description" in e

    def test_get_events(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.get(f"/api/player/sessions/{sid}/events")
        assert resp.status_code == 200
        assert "events" in resp.json()

    def test_get_combat_not_in_combat(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.get(f"/api/player/sessions/{sid}/combat")
        assert resp.status_code == 200
        data = resp.json()
        assert data["in_combat"] is False
        assert data["combat"] is None

    def test_get_map(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.get(f"/api/player/sessions/{sid}/map")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_region" in data
        assert "paths" in data
        assert len(data["paths"]) > 0
        path = data["paths"][0]
        assert "target_id" in path
        assert "target_name" in path
        assert "distance_m" in path
        assert "travel_seconds" in path

    def test_perception_no_player(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        # Create session without player (sword_vale has no player.yaml)
        resp = client.post("/api/master/sessions", json={"world_name": "sword_vale"})
        sid = resp.json()["session_id"]

        resp = client.get(f"/api/player/sessions/{sid}/perception")
        assert resp.status_code == 404


class TestLanguage:
    def test_create_session_with_lang(self, tmp_path: object) -> None:
        client, service = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={"lang": "ru"})
        assert resp.status_code == 200
        sid = resp.json()["session_id"]
        session = service.get_session(sid)
        assert session.lang == "ru"

    def test_change_lang(self, tmp_path: object) -> None:
        client, service = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.put(f"/api/master/sessions/{sid}/lang", json={"lang": "ru"})
        assert resp.status_code == 200

        session = service.get_session(sid)
        assert session.lang == "ru"

    def test_default_lang_is_en(self, tmp_path: object) -> None:
        client, service = _make_client(tmp_path)
        sid = _create_session(client)
        session = service.get_session(sid)
        assert session.lang == "en"


class TestSaves:
    def test_save_and_list(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        # Save
        resp = client.post(f"/api/master/sessions/{sid}/save")
        assert resp.status_code == 200
        assert "Saved" in resp.json()["message"]

        # List
        resp = client.get(f"/api/master/sessions/{sid}/saves")
        assert resp.status_code == 200
        assert len(resp.json()["saves"]) >= 1

    def test_save_with_name(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.post(f"/api/master/sessions/{sid}/save?name=my_save")
        assert resp.status_code == 200
        assert "my_save" in resp.json()["message"]

        resp = client.get(f"/api/master/sessions/{sid}/saves")
        assert "my_save" in resp.json()["saves"]

    def test_save_and_load(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        # Advance time then save
        client.post(f"/api/master/sessions/{sid}/time/advance", json={"hours": 12})
        client.post(f"/api/master/sessions/{sid}/save?name=checkpoint")

        # Advance more time
        client.post(f"/api/master/sessions/{sid}/time/advance", json={"hours": 24})

        # Load checkpoint
        resp = client.post(f"/api/master/sessions/{sid}/saves/checkpoint/load")
        assert resp.status_code == 200

    def test_load_nonexistent_save(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.post(f"/api/master/sessions/{sid}/saves/nope/load")
        assert resp.status_code == 404
