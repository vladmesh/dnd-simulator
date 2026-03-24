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


def _create_session_with_player(client: TestClient) -> str:
    sid = _create_session(client)
    resp = client.post(
        f"/api/player/sessions/{sid}/character", json={"name": "Tester", "race": "human", "char_class": "fighter"}
    )
    assert resp.status_code == 200
    return sid


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
        resp = client.post("/api/master/sessions", json={"world_name": "sword_vale"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data

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


class TestCreatureHotControls:
    def test_list_creatures(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/master/sessions/{sid}/creatures")
        assert resp.status_code == 200
        creatures = resp.json()
        # Should include NPCs + player from sword_vale template
        assert len(creatures) >= 3
        assert any(c["id"] == "edgar" for c in creatures)

    def test_list_creatures_filter_npc(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/master/sessions/{sid}/creatures?entity_type=npc")
        assert resp.status_code == 200
        creatures = resp.json()
        assert all(c["entity_type"] == "npc" for c in creatures)

    def test_list_creatures_filter_player(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)
        resp = client.get(f"/api/master/sessions/{sid}/creatures?entity_type=player")
        assert resp.status_code == 200
        creatures = resp.json()
        assert len(creatures) == 1
        assert creatures[0]["entity_type"] == "player"

    def test_get_creature(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/master/sessions/{sid}/creatures/edgar")
        assert resp.status_code == 200
        creature = resp.json()
        assert creature["name"] == "Edgar the Smith"
        assert creature["entity_type"] == "npc"

    def test_spawn_npc(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/master/sessions/{sid}/creatures",
            json={
                "id": "goblin_scout",
                "name": "Goblin Scout",
                "entity_type": "npc",
                "start_location": "silverport_city_gate",
                "role": "guard",
                "hp": 7,
                "ac": 13,
                "speed": 30,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == "goblin_scout"

        # Verify it shows up
        resp = client.get(f"/api/master/sessions/{sid}/creatures/goblin_scout")
        assert resp.status_code == 200

    def test_spawn_monster(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/master/sessions/{sid}/creatures",
            json={
                "id": "wolf_1",
                "name": "Dire Wolf",
                "entity_type": "monster",
                "start_location": "silverport_city_gate",
                "hp": 37,
                "ac": 14,
                "speed": 30,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "wolf_1"
        assert data["name"] == "Dire Wolf"

    def test_patch_creature(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.patch(
            f"/api/master/sessions/{sid}/creatures/edgar",
            json={"current_hp": 5, "personality": "Now angry"},
        )
        assert resp.status_code == 200

        resp = client.get(f"/api/master/sessions/{sid}/creatures/edgar")
        creature = resp.json()
        assert creature["hp"] == 5
        assert "angry" in creature["personality"].lower()

    def test_patch_player_forbidden(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.patch(
            f"/api/master/sessions/{sid}/creatures/player",
            json={"current_hp": 1},
        )
        assert resp.status_code == 400

    def test_delete_creature(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.delete(f"/api/master/sessions/{sid}/creatures/edgar")
        assert resp.status_code == 200

        resp = client.get(f"/api/master/sessions/{sid}/creatures/edgar")
        assert resp.status_code == 404

    def test_delete_player_forbidden(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.delete(f"/api/master/sessions/{sid}/creatures/player")
        assert resp.status_code == 400

    def test_set_brain_rule_based(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.put(
            f"/api/master/sessions/{sid}/creatures/edgar/brain",
            json={"type": "rule_based"},
        )
        assert resp.status_code == 200

    def test_set_brain_llm_no_config(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.put(
            f"/api/master/sessions/{sid}/creatures/edgar/brain",
            json={"type": "llm"},
        )
        assert resp.status_code == 400  # LLM not configured

    def test_set_brain_player_forbidden(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.put(
            f"/api/master/sessions/{sid}/creatures/player/brain",
            json={"type": "rule_based"},
        )
        assert resp.status_code == 400


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
        sid = _create_session_with_player(client)
        resp = client.get(f"/api/player/sessions/{sid}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] != ""
        assert data["hp"] > 0
        assert "str" in data["ability_scores"]


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
                "start_location": "silverport_city_tavern",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Thrain"
        assert data["race"] == "dwarf"
        assert data["hp"] == 14
        assert data["location_id"] == "silverport_city_tavern"

    def test_create_character_default_region(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = self._create_session_no_player(client)

        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={"name": "Nobody"},
        )
        assert resp.status_code == 200
        assert resp.json()["location_id"] != ""

    def test_create_multiple_players(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = self._create_session_no_player(client)

        resp1 = client.post(f"/api/player/sessions/{sid}/character", json={"name": "First"})
        resp2 = client.post(f"/api/player/sessions/{sid}/character", json={"name": "Second"})
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Each player gets a unique ID
        assert resp1.json()["player_id"] != resp2.json()["player_id"]

    def test_status_without_player(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = self._create_session_no_player(client)

        resp = client.get(f"/api/player/sessions/{sid}/status")
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
