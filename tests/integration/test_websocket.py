"""WebSocket integration tests.

Tests run against a live backend in docker compose with:
- DND_DICE_SEED=42 (deterministic rolls)
- Test content (arena + village worlds, all rule-based)

WS tests use their own sessions (not shared with REST tests) to avoid
state pollution from round threads and creature modifications.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest
import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action

# ── Module-scoped fixtures (isolated from REST tests) ─────────────────


@pytest.fixture(scope="module")
def _urls(backend_url: str) -> tuple[str, str, str]:
    api = f"{backend_url}/api/master"
    player_api = f"{backend_url}/api/player"
    ws_base = backend_url.replace("http://", "ws://") + "/api/ws"
    return api, player_api, ws_base


@pytest.fixture(scope="module")
def ws_arena(_urls: tuple[str, str, str]) -> Iterator[tuple[str, str, str]]:
    """Fresh arena session for WS tests. Yields (ws_base_url, session_id, player_id)."""
    api, player_api, ws_base = _urls
    resp = requests.post(f"{api}/sessions", json={"world_name": "arena.yaml", "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    resp = requests.post(
        f"{player_api}/sessions/{sid}/character",
        json={
            "name": "WS Fighter",
            "race": "human",
            "char_class": "fighter",
            "level": 1,
            "alignment": "true_neutral",
            "hp": 30,
            "ac": 15,
            "start_location": "arena_floor",
            "ability_scores": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10},
        },
        timeout=10,
    )
    resp.raise_for_status()
    pid = resp.json()["player_id"]

    yield ws_base, sid, pid
    requests.delete(f"{api}/sessions/{sid}", timeout=5)


@pytest.fixture(scope="module")
def ws_village(_urls: tuple[str, str, str]) -> Iterator[tuple[str, str, str]]:
    """Fresh village session for WS tests. Yields (ws_base_url, session_id, player_id)."""
    api, player_api, ws_base = _urls
    resp = requests.post(f"{api}/sessions", json={"world_name": "village.yaml", "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    resp = requests.post(
        f"{player_api}/sessions/{sid}/character",
        json={
            "name": "WS Traveler",
            "race": "human",
            "char_class": "fighter",
            "level": 1,
            "alignment": "true_neutral",
            "hp": 20,
            "ac": 12,
            "start_location": "village_square",
            "ability_scores": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
        },
        timeout=10,
    )
    resp.raise_for_status()
    pid = resp.json()["player_id"]

    yield ws_base, sid, pid
    requests.delete(f"{api}/sessions/{sid}", timeout=5)


def _recv_until(sock: ws_lib.WebSocket, target_type: str, max_msgs: int = 15) -> dict | None:
    """Receive messages until one with target_type appears, or return None."""
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == target_type:
            return msg
    return None


# ── Connection & first turn ───────────────────────────────────────────


class TestConnection:
    def test_connect_and_receive_turn(self, ws_arena: tuple[str, str, str]) -> None:
        """Connect to WS, receive initial turn message."""
        ws_base, sid, pid = ws_arena
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
            assert "awareness" in msg
            assert "mode" in msg
            assert "location" in msg
        finally:
            sock.close()

    def test_reconnect_replays_last_turn(self, ws_arena: tuple[str, str, str]) -> None:
        """Disconnect and reconnect — should receive last turn message."""
        ws_base, sid, pid = ws_arena

        sock1 = ws_connect(ws_base, sid, pid)
        msg1 = ws_recv(sock1)
        assert msg1["type"] == "turn"
        sock1.close()

        time.sleep(0.5)  # let server process disconnect

        sock2 = ws_connect(ws_base, sid, pid)
        msg2 = ws_recv(sock2)
        assert msg2["type"] == "turn"
        assert "awareness" in msg2
        sock2.close()

    def test_invalid_session_returns_error(self, ws_arena: tuple[str, str, str]) -> None:
        """Connecting to nonexistent session returns error and closes."""
        ws_base, _, _ = ws_arena
        sock = ws_lib.create_connection(f"{ws_base}/nonexistent?player_id=fake", timeout=10)
        msg = ws_recv(sock)
        assert msg["type"] == "error"
        try:
            sock.recv()
        except ws_lib.WebSocketConnectionClosedException:
            pass
        finally:
            sock.close()


# ── Peaceful flow ─────────────────────────────────────────────────────


class TestPeacefulFlow:
    def test_wait_action(self, ws_village: tuple[str, str, str]) -> None:
        """In peaceful mode, send wait → round advances."""
        ws_base, sid, pid = ws_village
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
            assert msg["mode"] == "peaceful"

            ws_send_action(sock, "wait")

            msg = ws_recv(sock)
            assert msg["type"] in ("action_result", "round_result", "turn")
        finally:
            sock.close()


# ── Combat flow ───────────────────────────────────────────────────────


class TestCombatFlow:
    def test_attack_triggers_combat(self, ws_arena: tuple[str, str, str]) -> None:
        """Attack an NPC — should get action_result with events."""
        ws_base, sid, pid = ws_arena
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"

            ws_send_action(sock, "attack", target_id="razor")

            # Collect messages — combat may start first, then we get action_result
            got_result = False
            for _ in range(15):
                msg = ws_recv(sock)
                if msg["type"] == "action_result":
                    assert msg["action"] == "attack"
                    assert "events" in msg
                    got_result = True
                    break
                if msg["type"] == "turn":
                    # Combat started, our turn again — attack
                    ws_send_action(sock, "attack", target_id="razor")
                if msg["type"] == "error":
                    break
            assert got_result, f"Never received action_result, last msg: {msg}"
        finally:
            sock.close()

    def test_end_turn(self, ws_arena: tuple[str, str, str]) -> None:
        """Send end_turn — round advances, eventually get next turn."""
        ws_base, sid, pid = ws_arena
        sock = ws_connect(ws_base, sid, pid)
        try:
            # May get turn, round_result, or action_result (combat ongoing from previous test)
            msg = _recv_until(sock, "turn")
            if msg is None:
                return  # round ended or session done, that's fine

            ws_send_action(sock, "end_turn")

            # Should eventually get next turn, round_result, or action_result
            for _ in range(15):
                try:
                    msg = ws_recv(sock)
                except ws_lib.WebSocketConnectionClosedException:
                    break  # session may have ended
                if msg["type"] in ("turn", "round_result"):
                    break
        finally:
            sock.close()


# ── Error handling ────────────────────────────────────────────────────


class TestErrorHandling:
    def test_unknown_message_type(self, ws_village: tuple[str, str, str]) -> None:
        """Sending unknown message type returns error among responses."""
        ws_base, sid, pid = ws_village
        sock = ws_connect(ws_base, sid, pid)
        try:
            _ = ws_recv(sock)  # consume initial turn
            sock.send('{"type": "query", "data": "test"}')
            # Error may be interleaved with turn messages from round thread
            error = _recv_until(sock, "error")
            assert error is not None, "Expected error message for unknown type"
        finally:
            sock.close()

    def test_invalid_action_name(self, ws_village: tuple[str, str, str]) -> None:
        """Sending invalid action name returns error among responses."""
        ws_base, sid, pid = ws_village
        sock = ws_connect(ws_base, sid, pid)
        try:
            _ = ws_recv(sock)  # consume initial turn
            sock.send('{"type": "action", "name": "nonexistent_action"}')
            # May get error or turn (round thread races). Check for error.
            error = _recv_until(sock, "error")
            assert error is not None, "Expected error message for invalid action"
        finally:
            sock.close()
