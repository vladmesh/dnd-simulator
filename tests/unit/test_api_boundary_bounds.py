"""API boundary bounds: frontend error reports, WS message size, action params, GM request schemas."""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path

import pytest
import structlog
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api import app as app_module
from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.adapters.api.routes_ws import MAX_WS_MESSAGE_BYTES
from dnd_simulator.adapters.api.schemas import MAX_LAYER_FILE_CHARS
from dnd_simulator.core.action import ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import EventType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities import combat_resolution
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.rules.checks import CheckResult
from dnd_simulator.rules.combat import AttackResult
from dnd_simulator.service import GameService
from dnd_simulator.service.action_parsing import (
    MAX_ACTION_PARAMS,
    MAX_PARAM_STRING_LENGTH,
    ActionParamsError,
    parse_action,
)
from dnd_simulator.storage.store import JsonFileStore


def _client(tmp_path: Path) -> tuple[TestClient, GameService]:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    set_service(service)
    return TestClient(app), service


def _session_with_player(client: TestClient) -> str:
    response = client.post("/api/master/sessions", json={})
    assert response.status_code == HTTPStatus.OK
    sid = str(response.json()["session_id"])
    response = client.post(
        f"/api/player/sessions/{sid}/character",
        json={
            "name": "Tester",
            "race": "human",
            "char_class": "fighter",
            "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
        },
    )
    assert response.status_code == HTTPStatus.OK
    return sid


def _entities(service: GameService, sid: str) -> EntitiesLayer:
    return service._get_entities_layer(service._get_session(sid))


# -- POST /api/frontend-error --


class TestFrontendErrorReport:
    def test_reporter_payloads_are_logged(self, tmp_path: Path) -> None:
        client, _ = _client(tmp_path)
        # main.tsx sends {message, stack}; ErrorBoundary adds the React component stack.
        for body in (
            {"message": "boom", "stack": "Error: boom\n    at x"},
            {"message": "boom", "stack": "Error: boom", "component": "\n    in App"},
            {"message": "rejected"},
        ):
            with structlog.testing.capture_logs() as logs:
                response = client.post("/api/frontend-error", json=body)
            assert response.status_code == HTTPStatus.OK, response.text
            assert response.json() == {"status": "logged"}
            entry = next(log for log in logs if log["event"] == "frontend_error")
            assert entry["message"] == body["message"]

    def test_logged_fields_are_truncated(self, tmp_path: Path) -> None:
        client, _ = _client(tmp_path)
        stack = "x" * (app_module.FRONTEND_ERROR_LOG_CHARS + 500)

        with structlog.testing.capture_logs() as logs:
            response = client.post("/api/frontend-error", json={"message": "m", "stack": stack})

        assert response.status_code == HTTPStatus.OK
        entry = next(log for log in logs if log["event"] == "frontend_error")
        assert len(entry["stack"]) < len(stack)
        assert entry["stack"].startswith("x" * app_module.FRONTEND_ERROR_LOG_CHARS)
        assert "truncated 500 chars" in entry["stack"]

    @pytest.mark.parametrize("body", ['{"message": 5}', '{"message": "m", "stack": ["a"]}', "[]", "not json"])
    def test_invalid_body_is_422(self, tmp_path: Path, body: str) -> None:
        client, _ = _client(tmp_path)
        response = client.post("/api/frontend-error", content=body, headers={"Content-Type": "application/json"})
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_overlong_field_is_422(self, tmp_path: Path) -> None:
        client, _ = _client(tmp_path)
        response = client.post("/api/frontend-error", json={"message": "m" * (8 * 1024 + 1)})
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_oversized_body_is_413(self, tmp_path: Path) -> None:
        client, _ = _client(tmp_path)
        padding = "p" * (app_module.MAX_FRONTEND_ERROR_BYTES + 1)
        response = client.post(
            "/api/frontend-error",
            content=json.dumps({"message": "m", "junk": padding}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE


# -- WebSocket message size and params --


class TestWsMessageSize:
    def test_oversized_player_message_is_rejected_and_loop_survives(self, tmp_path: Path) -> None:
        client, _ = _client(tmp_path)
        sid = _session_with_player(client)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            assert ws.receive_json()["type"] == "turn"
            oversized = json.dumps({"type": "action", "name": "end_turn", "pad": "x" * MAX_WS_MESSAGE_BYTES})
            ws.send_text(oversized)
            error = ws.receive_json()
            assert error["type"] == "error"
            assert str(MAX_WS_MESSAGE_BYTES) in error["message"]

            ws.send_json({"type": "action", "name": "end_turn"})
            assert ws.receive_json()["type"] == "round_result"

    def test_multibyte_message_is_measured_in_bytes(self, tmp_path: Path) -> None:
        client, _ = _client(tmp_path)
        sid = _session_with_player(client)
        # Fewer characters than the limit, more UTF-8 bytes than it.
        pad = "я" * (MAX_WS_MESSAGE_BYTES // 2 + 1)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            assert ws.receive_json()["type"] == "turn"
            ws.send_text(json.dumps({"type": "action", "name": "end_turn", "pad": pad}, ensure_ascii=False))
            error = ws.receive_json()
            assert error["type"] == "error"
            assert str(MAX_WS_MESSAGE_BYTES) in error["message"]

    def test_oversized_spectator_message_is_rejected(self, tmp_path: Path) -> None:
        client, _ = _client(tmp_path)
        sid = _session_with_player(client)

        with client.websocket_connect(f"/api/ws/{sid}?spectate=true") as ws:
            ws.send_text("x" * (MAX_WS_MESSAGE_BYTES + 1))
            error = ws.receive_json()
            assert error["type"] == "error"
            assert str(MAX_WS_MESSAGE_BYTES) in error["message"]
            ws.send_json({"type": "ping"})
            assert "Unknown" in ws.receive_json()["message"]

    @pytest.mark.parametrize(
        ("params", "fragment"),
        [
            ("attack", "object"),
            (["target_id"], "object"),
            ({"text": "x" * (MAX_PARAM_STRING_LENGTH + 1)}, "too large"),
        ],
    )
    def test_bad_params_get_a_protocol_error(self, tmp_path: Path, params: object, fragment: str) -> None:
        client, _ = _client(tmp_path)
        sid = _session_with_player(client)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            assert ws.receive_json()["type"] == "turn"
            ws.send_json({"type": "action", "name": "dodge", "params": params})
            error = ws.receive_json()
            assert error["type"] == "error"
            assert fragment in error["message"].lower()

            ws.send_json({"type": "action", "name": "end_turn"})
            assert ws.receive_json()["type"] == "round_result"


class TestParseActionParams:
    @pytest.mark.parametrize("params", ["x", 1, ["a"], True])
    def test_non_object_params_are_rejected(self, params: object) -> None:
        with pytest.raises(ActionParamsError) as exc_info:
            parse_action({"name": "dodge", "params": params}, default_name="idle")
        assert exc_info.value.reason == "not_object"

    def test_non_string_keys_are_rejected(self) -> None:
        with pytest.raises(ActionParamsError) as exc_info:
            parse_action({"name": "dodge", "params": {1: "x"}}, default_name="idle")
        assert exc_info.value.reason == "not_object"

    def test_too_many_params_are_rejected(self) -> None:
        params = {f"p{i}": i for i in range(MAX_ACTION_PARAMS + 1)}
        with pytest.raises(ActionParamsError) as exc_info:
            parse_action({"name": "dodge", "params": params}, default_name="idle")
        assert exc_info.value.reason == "too_large"

    def test_overlong_string_param_is_rejected(self) -> None:
        with pytest.raises(ActionParamsError) as exc_info:
            parse_action({"name": "say", "params": {"text": "x" * (MAX_PARAM_STRING_LENGTH + 1)}}, default_name="idle")
        assert exc_info.value.reason == "too_large"

    def test_null_params_and_bounded_params_are_accepted(self) -> None:
        assert parse_action({"name": "dodge", "params": None}, default_name="idle").params == {}
        text = "x" * MAX_PARAM_STRING_LENGTH
        action = parse_action({"name": "say", "params": {"target_id": "n", "text": text}}, default_name="idle")
        assert action.name is ActionType.SAY
        assert action.params == {"target_id": "n", "text": text}


# -- GM request schemas --


class TestLayerFileBound:
    def test_oversized_layer_file_is_rejected_before_the_service(self, tmp_path: Path) -> None:
        client, _ = _client(tmp_path)
        response = client.put(
            "/api/master/worlds/sword_vale/layers/geography/files/locations.yaml",
            json={"content": "a" * (MAX_LAYER_FILE_CHARS + 1)},
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert response.json()["detail"][0]["loc"] == ["body", "content"]


class TestGiveItemBounds:
    @pytest.mark.parametrize(
        "extra",
        [
            {"price": -1},
            {"reach": 0},
            {"reach": 1000},
            {"base_ac": -5},
            {"base_ac": 99},
            {"max_dex_bonus": -1},
            {"strength_req": 99},
            {"ac_bonus": -1},
            {"ac_bonus": 50},
            {"name": "n" * 201},
            {"grant_actions": ["a"] * 17},
            {"damage": [{"dice": "1d4", "type": "fire"}] * 9},
        ],
    )
    def test_out_of_range_fields_are_422(self, tmp_path: Path, extra: dict[str, object]) -> None:
        client, service = _client(tmp_path)
        sid = _session_with_player(client)
        player = next(e for e in _entities(service, sid)._entities.values() if isinstance(e, PlayerCharacter))
        before = list(player.inventory)

        response = client.post(
            f"/api/master/sessions/{sid}/creatures/{player.id}/items",
            json={"name": "Thing", "type": "potion", "heal_dice": "1d4", **extra},
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
        assert player.inventory == before

    def test_in_range_weapon_is_given(self, tmp_path: Path) -> None:
        client, service = _client(tmp_path)
        sid = _session_with_player(client)
        player = next(e for e in _entities(service, sid)._entities.values() if isinstance(e, PlayerCharacter))

        response = client.post(
            f"/api/master/sessions/{sid}/creatures/{player.id}/items",
            json={
                "name": "Glaive",
                "type": "weapon",
                "weapon_id": "glaive",
                "attack_name": "Glaive",
                "category": "martial",
                "damage": [{"dice": "1d10", "type": "slashing"}],
                "reach": 10,
                "price": 20,
            },
        )

        assert response.status_code == HTTPStatus.OK, response.text


def _hit() -> AttackResult:
    return AttackResult(
        hit=True,
        critical=False,
        attack_check=CheckResult(success=True, roll=15, total=20, dc=10, critical=False),
        damage=(),
        total_damage=10,
    )


class TestSpawnXpValue:
    @pytest.mark.parametrize("entity_type", ["monster", "npc"])
    def test_spawned_creature_awards_its_xp_value_on_kill(self, tmp_path: Path, entity_type: str) -> None:
        client, service = _client(tmp_path)
        sid = _session_with_player(client)
        layer = _entities(service, sid)
        player = next(e for e in layer._entities.values() if isinstance(e, PlayerCharacter))
        xp_before = player.experience

        response = client.post(
            f"/api/master/sessions/{sid}/creatures",
            json={
                "id": "ogre",
                "name": "Ogre",
                "entity_type": entity_type,
                "start_location": player.location_id,
                "hp": 20,
                "ac": 11,
                "speed": 30,
                "xp_value": 450,
            },
        )
        assert response.status_code == HTTPStatus.OK, response.text
        ogre = layer.get_entity("ogre")
        assert isinstance(ogre, Creature)
        assert ogre.xp_value == 450

        ogre.current_hp = 0
        combat_resolution.handle_death(layer._combat, player, ogre, ogre.id, _hit())

        assert player.experience == xp_before + 450
        assert any(event.event_type is EventType.XP_GAINED for event in layer._location_log[player.location_id])

    def test_negative_xp_value_is_422(self, tmp_path: Path) -> None:
        client, service = _client(tmp_path)
        sid = _session_with_player(client)
        response = client.post(
            f"/api/master/sessions/{sid}/creatures",
            json={
                "id": "ogre",
                "name": "Ogre",
                "entity_type": "monster",
                "start_location": "anywhere",
                "hp": 20,
                "ac": 11,
                "speed": 30,
                "xp_value": -1,
            },
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert _entities(service, sid).get_entity("ogre") is None
