"""Tests for the WebSocket game endpoint."""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.core.character import Creature
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.rules.rule_brain import RuleBrain
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _make_client(tmp_path: object) -> tuple[TestClient, GameService]:
    store = JsonFileStore(Path(str(tmp_path)) / "saves")
    service = GameService(store=store)
    set_service(service)
    return TestClient(app), service


def _create_session_with_player(client: TestClient) -> str:
    resp = client.post("/api/master/sessions", json={})
    assert resp.status_code == HTTPStatus.OK
    sid = resp.json()["session_id"]
    resp = client.post(
        f"/api/player/sessions/{sid}/character",
        json={
            "name": "Tester",
            "race": "human",
            "char_class": "fighter",
            "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
        },
    )
    assert resp.status_code == HTTPStatus.OK
    return sid


class TestWebSocketErrors:
    def test_invalid_session(self, tmp_path: object) -> None:
        """WS to nonexistent session sends error."""
        client, _ = _make_client(tmp_path)
        with client.websocket_connect("/api/ws/nonexistent") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["message"]

    def test_no_player(self, tmp_path: object) -> None:
        """WS to session without player sends error."""
        client, service = _make_client(tmp_path)
        resp = client.post("/api/master/sessions", json={})
        sid = resp.json()["session_id"]
        # Remove player from entities layer
        session = service.get_session(sid)
        from dnd_simulator.layers.entities.layer import EntitiesLayer

        for layer in session.world.layers:
            if isinstance(layer, EntitiesLayer):
                layer.remove_entity("player")
                break
        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "player" in msg["message"].lower()


class TestWebSocketTurnCycle:
    def test_wait_fast_forwards_past_nearby_rule_npc(self, tmp_path: object) -> None:
        client, service = _make_client(tmp_path)
        sid = _create_session_with_player(client)
        session = service.get_session(sid)
        entities = next(layer for layer in session.world.layers if isinstance(layer, EntitiesLayer))
        player = next(entity for entity in entities._entities.values() if isinstance(entity, PlayerCharacter))
        entities.add_entity(
            Creature(
                id="bystander",
                name="Bystander",
                location_id=player.location_id,
                brain=RuleBrain(),
            )
        )
        started_at = session.world.time.to_total_seconds()

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            assert ws.receive_json()["type"] == "turn"
            ws.send_json({"type": "action", "name": "wait", "params": {"hours": 1}})

            messages = []
            for _ in range(6):
                message = ws.receive_json()
                messages.append(message)
                if message["type"] == "turn":
                    break

        assert messages[-1]["type"] == "turn"
        assert not any(message.get("actor") == "bystander" for message in messages)
        assert session.world.time.to_total_seconds() >= started_at + 3600

    def test_receive_turn_send_end_turn(self, tmp_path: object) -> None:
        """Connect WS, receive turn awareness, send end_turn, receive round_result."""
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            # Should receive a turn message (player's first turn)
            msg = ws.receive_json()
            assert msg["type"] == "turn"
            assert msg["mode"] in ("peaceful", "combat")
            assert "awareness" in msg
            assert "events" in msg

            # Send end_turn to finish turn without doing anything
            ws.send_json({"type": "action", "name": "end_turn"})

            # Should receive round_result
            msg = ws.receive_json()
            assert msg["type"] == "round_result"
            assert "events" in msg

            # Should receive next turn
            msg = ws.receive_json()
            assert msg["type"] == "turn"

    def test_action_then_end_turn(self, tmp_path: object) -> None:
        """Send a say action (turn-ending in peaceful), get action_result then round_result."""
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            # First turn (peaceful)
            msg = ws.receive_json()
            assert msg["type"] == "turn"

            # Send a say action — turn-ending in peaceful mode
            ws.send_json({"type": "action", "name": "say", "params": {"text": "hello"}})

            # Should get action_result (no budget in peaceful)
            msg = ws.receive_json()
            assert msg["type"] == "action_result"
            assert msg["action"] == "say"
            assert "budget" not in msg  # no budget in peaceful mode

            # Say auto-ends peaceful turn → round completes → round_result
            msg = ws.receive_json()
            assert msg["type"] == "round_result"

            # NPC actions may produce action_result messages before next turn
            msg = ws.receive_json()
            while msg["type"] == "action_result":
                msg = ws.receive_json()
            assert msg["type"] == "turn"

    def test_unknown_message_type(self, tmp_path: object) -> None:
        """Unknown message type returns error."""
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            # Receive turn first
            ws.receive_json()

            ws.send_json({"type": "invalid"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "Unknown" in msg["message"]

    def test_query_type_rejected(self, tmp_path: object) -> None:
        """Query message type is not supported — returns error."""
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            ws.receive_json()  # turn

            ws.send_json({"type": "query", "name": "look"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "Unknown" in msg["message"]

    def test_non_object_json_returns_protocol_error_without_closing_player_socket(self, tmp_path: object) -> None:
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            assert ws.receive_json()["type"] == "turn"

            for raw in ("[]", "null", json.dumps("text"), "1"):
                ws.send_text(raw)
                error = ws.receive_json()
                assert error["type"] == "error"
                assert "object" in error["message"].lower()

            ws.send_text("{not json")
            error = ws.receive_json()
            assert error == {"type": "error", "message": "Invalid JSON"}

            ws.send_json({"type": "action", "name": "end_turn"})
            assert ws.receive_json()["type"] == "round_result"
