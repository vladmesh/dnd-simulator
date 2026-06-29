from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _make_client(tmp_path: object, *, isolated_content: bool = False) -> tuple[TestClient, GameService]:
    tmp = Path(str(tmp_path))
    store = JsonFileStore(tmp / "saves")
    if isolated_content:
        # Create an isolated content dir with symlinked library and worlds
        from dnd_simulator.service.game_service import DEFAULT_CONTENT_DIR

        content_dir = tmp / "content"
        content_dir.mkdir()
        (content_dir / "library").symlink_to(DEFAULT_CONTENT_DIR / "library")
        catalogs_src = DEFAULT_CONTENT_DIR / "catalogs"
        if catalogs_src.exists():
            (content_dir / "catalogs").symlink_to(catalogs_src)
        (content_dir / "worlds").mkdir()
        # Copy existing worlds so we can fork without mutating real content
        import shutil

        for world in (DEFAULT_CONTENT_DIR / "worlds").iterdir():
            if world.is_dir():
                shutil.copytree(world, content_dir / "worlds" / world.name)
        service = GameService(store=store, content_dir=content_dir)
    else:
        service = GameService(store=store)
    set_service(service)
    return TestClient(app), service


def _create_session(client: TestClient) -> str:
    resp = client.post("/api/master/sessions", json={})
    assert resp.status_code == HTTPStatus.OK
    return resp.json()["session_id"]


_DEFAULT_SCORES = {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8}


def _create_session_with_player(client: TestClient) -> str:
    sid = _create_session(client)
    resp = client.post(
        f"/api/player/sessions/{sid}/character",
        json={"name": "Tester", "race": "human", "char_class": "fighter", "ability_scores": _DEFAULT_SCORES},
    )
    assert resp.status_code == HTTPStatus.OK
    return sid


class TestHealthEndpoint:
    def test_health(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.get("/health")
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["status"] == "ok"


class TestWorldsEndpoint:
    def test_list_worlds(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds")
        assert resp.status_code == HTTPStatus.OK
        worlds = resp.json()
        assert len(worlds) >= 1
        assert any(w["id"] == "sword_vale" for w in worlds)

    def test_list_worlds_has_editable_field(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds")
        assert resp.status_code == HTTPStatus.OK
        worlds = resp.json()
        # Every world has an editable field
        for w in worlds:
            assert "editable" in w, f"World {w['id']} missing 'editable' field"
        # Base world sword_vale is NOT editable
        sword_vale = next(w for w in worlds if w["id"] == "sword_vale")
        assert sword_vale["editable"] is False

    def test_forked_world_is_editable(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path, isolated_content=True)
        # Fork sword_vale
        resp = client.post(
            "/api/master/worlds/sword_vale/fork",
            json={"new_id": "my_world"},
        )
        assert resp.status_code == HTTPStatus.CREATED
        # List worlds — forked world should be editable
        resp = client.get("/api/master/worlds")
        worlds = resp.json()
        my_world = next(w for w in worlds if w["id"] == "my_world")
        assert my_world["editable"] is True


class TestMasterSessions:
    def test_create_session(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={"world_name": "sword_vale"})
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert "session_id" in data

    def test_get_session_state(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/master/sessions/{sid}")
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert len(data["regions"]) > 0
        assert len(data["entities"]) > 0

    def test_delete_session(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.delete(f"/api/master/sessions/{sid}")
        assert resp.status_code == HTTPStatus.OK
        # Session should be gone
        resp = client.get(f"/api/master/sessions/{sid}")
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_get_nonexistent_session(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.get("/api/master/sessions/doesnotexist")
        assert resp.status_code == HTTPStatus.NOT_FOUND


class TestCreatureHotControls:
    def test_list_creatures(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/master/sessions/{sid}/creatures")
        assert resp.status_code == HTTPStatus.OK
        creatures = resp.json()
        # Should include NPCs + player from sword_vale template
        assert len(creatures) >= 3
        assert any(c["id"] == "edgar" for c in creatures)

    def test_list_creatures_filter_npc(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/master/sessions/{sid}/creatures?entity_type=npc")
        assert resp.status_code == HTTPStatus.OK
        creatures = resp.json()
        assert all(c["entity_type"] == "npc" for c in creatures)

    def test_list_creatures_filter_player(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)
        resp = client.get(f"/api/master/sessions/{sid}/creatures?entity_type=player")
        assert resp.status_code == HTTPStatus.OK
        creatures = resp.json()
        assert len(creatures) == 1
        assert creatures[0]["entity_type"] == "player"

    def test_get_creature(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.get(f"/api/master/sessions/{sid}/creatures/edgar")
        assert resp.status_code == HTTPStatus.OK
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
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["id"] == "goblin_scout"

        # Verify it shows up
        resp = client.get(f"/api/master/sessions/{sid}/creatures/goblin_scout")
        assert resp.status_code == HTTPStatus.OK

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
        assert resp.status_code == HTTPStatus.OK
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
        assert resp.status_code == HTTPStatus.OK

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
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_delete_creature(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.delete(f"/api/master/sessions/{sid}/creatures/edgar")
        assert resp.status_code == HTTPStatus.OK

        resp = client.get(f"/api/master/sessions/{sid}/creatures/edgar")
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_delete_player_forbidden(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.delete(f"/api/master/sessions/{sid}/creatures/player")
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_set_brain_rule_based(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.put(
            f"/api/master/sessions/{sid}/creatures/edgar/brain",
            json={"type": "rule_based"},
        )
        assert resp.status_code == HTTPStatus.OK

    def test_set_brain_llm_no_config_falls_back(self, tmp_path: object) -> None:
        """Switching to llm without LLM key falls back to RuleBrain and returns warning."""
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.put(
            f"/api/master/sessions/{sid}/creatures/edgar/brain",
            json={"type": "llm"},
        )
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert body["brain_type"] == "rule_based"
        assert body["warning"] == "no_llm_key"
        # ai_type reflects actual brain, not requested type
        info = client.get(f"/api/master/sessions/{sid}/creatures/edgar")
        assert info.json()["ai_type"] == "rule_based"

    def test_set_brain_player_forbidden(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.put(
            f"/api/master/sessions/{sid}/creatures/player/brain",
            json={"type": "rule_based"},
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST


class TestNationSettlementHotControls:
    def test_patch_nation(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.patch(
            f"/api/master/sessions/{sid}/nations/silverhold",
            json={"wealth": 100.0, "military": 80.0},
        )
        assert resp.status_code == HTTPStatus.OK

    def test_patch_nation_not_found(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.patch(
            f"/api/master/sessions/{sid}/nations/nonexistent",
            json={"wealth": 100.0},
        )
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_patch_settlement(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.patch(
            f"/api/master/sessions/{sid}/settlements/silverport_city",
            json={"population": 10000},
        )
        assert resp.status_code == HTTPStatus.OK


class TestTimeControl:
    def test_advance_time(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/master/sessions/{sid}/time/advance",
            json={"hours": 6},
        )
        assert resp.status_code == HTTPStatus.OK
        assert "Advanced 6h" in resp.json()["message"]


class TestPlayerEndpoints:
    def test_get_status(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)
        resp = client.get(f"/api/player/sessions/{sid}/status")
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["name"] != ""
        assert data["hp"] > 0
        assert "str" in data["ability_scores"]


class TestPlayerCharacterCreation:
    def _create_session_no_player(self, client: TestClient) -> str:
        resp = client.post("/api/master/sessions", json={"world_name": "sword_vale"})
        assert resp.status_code == HTTPStatus.OK
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
                "ability_scores": _DEFAULT_SCORES,
                "fighting_style": "defense",
                "start_location": "silverport_city_tavern",
            },
        )
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["name"] == "Thrain"
        assert data["race"] == "dwarf"
        assert data["max_hp"] == 12  # d10 + CON 14 (+2)
        assert data["gold"] == 1000
        assert data["location_id"] == "silverport_city_tavern"

    def test_create_character_default_region(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = self._create_session_no_player(client)

        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={"name": "Nobody", "ability_scores": _DEFAULT_SCORES},
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["location_id"] != ""

    def test_create_multiple_players(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = self._create_session_no_player(client)

        body = {"name": "First", "ability_scores": _DEFAULT_SCORES}
        resp1 = client.post(f"/api/player/sessions/{sid}/character", json=body)
        body2 = {"name": "Second", "ability_scores": _DEFAULT_SCORES}
        resp2 = client.post(f"/api/player/sessions/{sid}/character", json=body2)
        assert resp1.status_code == HTTPStatus.OK
        assert resp2.status_code == HTTPStatus.OK
        # Each player gets a unique ID
        assert resp1.json()["player_id"] != resp2.json()["player_id"]

    def test_status_without_player(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = self._create_session_no_player(client)

        resp = client.get(f"/api/player/sessions/{sid}/status")
        assert resp.status_code == HTTPStatus.NOT_FOUND


class TestLevelUpHTTPStatus:
    """Level-up route must map exceptions to HTTP status via type, not message text."""

    def test_level_up_unknown_session_returns_404(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/player/sessions/does_not_exist/level-up", json={})
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_level_up_no_player_returns_404(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)
        # Session exists but has no player character
        resp = client.post(f"/api/player/sessions/{sid}/level-up", json={})
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_level_up_no_pending_levelup_returns_400(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)
        # Player exists but level_up_available is False (default after creation)
        resp = client.post(f"/api/player/sessions/{sid}/level-up", json={})
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_level_up_invalid_fighting_style_returns_400(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)
        resp = client.post(f"/api/player/sessions/{sid}/level-up", json={"fighting_style": "not_a_style"})
        assert resp.status_code == HTTPStatus.BAD_REQUEST


class TestLanguage:
    def test_create_session_with_lang(self, tmp_path: object) -> None:
        client, service = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={"lang": "ru"})
        assert resp.status_code == HTTPStatus.OK
        sid = resp.json()["session_id"]
        session = service.get_session(sid)
        assert session.lang == "ru"

    def test_change_lang(self, tmp_path: object) -> None:
        client, service = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.put(f"/api/master/sessions/{sid}/lang", json={"lang": "ru"})
        assert resp.status_code == HTTPStatus.OK

        session = service.get_session(sid)
        assert session.lang == "ru"

    def test_default_lang_is_en(self, tmp_path: object) -> None:
        client, service = _make_client(tmp_path)
        sid = _create_session(client)
        session = service.get_session(sid)
        assert session.lang == "en"


class TestWorldManifest:
    def test_manifest_returns_layer_sources(self, tmp_path: object) -> None:
        """Manifest endpoint returns correct source/template/version for all layers."""
        client, _ = _make_client(tmp_path, isolated_content=True)
        # Assemble a fresh world so all layers are library-sourced
        resp = client.post(
            "/api/master/worlds/assemble",
            json={
                "id": "test_manifest",
                "name": "Test Manifest",
                "layer_selections": {
                    "geography": "sword_vale",
                    "politics": "sword_vale",
                    "settlements": "sword_vale",
                    "ecology": "sword_vale",
                    "entities": "sword_vale",
                },
                "default_player_faction": "kingdom",
            },
        )
        assert resp.status_code == HTTPStatus.CREATED

        resp = client.get("/api/master/worlds/test_manifest/manifest")
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["world_id"] == "test_manifest"
        assert data["name"] == "Test Manifest"
        layers = data["layers"]
        assert len(layers) == 5
        # All layers are library-sourced
        for layer in layers:
            assert layer["source"] == "library"
            assert layer["template"] == "sword_vale"
            assert layer["version"] == "1.0"
        # Canonical order
        layer_types = [ly["layer_type"] for ly in layers]
        assert layer_types == ["geography", "politics", "settlements", "ecology", "entities"]

    def test_manifest_mixed_library_custom(self, tmp_path: object) -> None:
        """After forking one layer, manifest shows mixed sources."""
        client, _ = _make_client(tmp_path, isolated_content=True)
        # Assemble a fresh world so all layers start as library
        resp = client.post(
            "/api/master/worlds/assemble",
            json={
                "id": "test_fork_mix",
                "name": "Test Fork Mix",
                "layer_selections": {
                    "geography": "sword_vale",
                    "politics": "sword_vale",
                    "settlements": "sword_vale",
                    "ecology": "sword_vale",
                    "entities": "sword_vale",
                },
                "default_player_faction": "kingdom",
            },
        )
        assert resp.status_code == HTTPStatus.CREATED

        # Fork geography layer
        resp = client.post("/api/master/worlds/test_fork_mix/fork/geography")
        assert resp.status_code == HTTPStatus.OK

        resp = client.get("/api/master/worlds/test_fork_mix/manifest")
        assert resp.status_code == HTTPStatus.OK
        layers = resp.json()["layers"]
        geo = next(ly for ly in layers if ly["layer_type"] == "geography")
        assert geo["source"] == "custom"
        assert geo["template"] is None
        assert geo["version"] is None
        # Other layers still library
        for layer in layers:
            if layer["layer_type"] != "geography":
                assert layer["source"] == "library"

    def test_manifest_404_for_nonexistent_world(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds/nonexistent/manifest")
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_manifest_all_five_layer_types_present(self, tmp_path: object) -> None:
        """All 5 layer types are always present in response, in canonical order."""
        client, _ = _make_client(tmp_path)
        resp = client.get("/api/master/worlds/sword_vale/manifest")
        assert resp.status_code == HTTPStatus.OK
        layer_types = {ly["layer_type"] for ly in resp.json()["layers"]}
        assert layer_types == {"geography", "politics", "settlements", "ecology", "entities"}


class TestSaves:
    def test_save_and_list(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        # Save
        resp = client.post(f"/api/master/sessions/{sid}/save")
        assert resp.status_code == HTTPStatus.OK
        assert "Saved" in resp.json()["message"]

        # List
        resp = client.get(f"/api/master/sessions/{sid}/saves")
        assert resp.status_code == HTTPStatus.OK
        assert len(resp.json()["saves"]) >= 1

    def test_save_with_name(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.post(f"/api/master/sessions/{sid}/save?name=my_save")
        assert resp.status_code == HTTPStatus.OK
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
        assert resp.status_code == HTTPStatus.OK

    def test_load_nonexistent_save(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session(client)

        resp = client.post(f"/api/master/sessions/{sid}/saves/nope/load")
        assert resp.status_code == HTTPStatus.NOT_FOUND
