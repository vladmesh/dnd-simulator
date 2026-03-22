"""Tests for the WebSocket game endpoint."""

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


def _create_session_with_player(client: TestClient) -> str:
    resp = client.post("/api/master/sessions", json={})
    assert resp.status_code == 200
    sid = resp.json()["session_id"]
    resp = client.post(
        f"/api/player/sessions/{sid}/character",
        json={"name": "Tester", "race": "human", "char_class": "fighter"},
    )
    assert resp.status_code == 200
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
        """Send a free action, get action_result + turn, then end_turn for round_result."""
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            # First turn
            msg = ws.receive_json()
            assert msg["type"] == "turn"

            # Send a say action (free, doesn't consume budget)
            ws.send_json({"type": "action", "name": "say", "params": {"text": "hello"}})

            # Should get action_result for the say
            msg = ws.receive_json()
            assert msg["type"] == "action_result"
            assert msg["action"] == "say"
            assert "budget" in msg

            # Loop continues — should get another turn prompt
            msg = ws.receive_json()
            assert msg["type"] == "turn"

            # Now end the turn
            ws.send_json({"type": "action", "name": "end_turn"})

            # Should receive round_result
            msg = ws.receive_json()
            assert msg["type"] == "round_result"

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
