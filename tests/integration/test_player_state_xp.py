"""Integration tests: XP fields in player state payload (REST + WS).

Sprint 017, Phase 1, Task 3 — verify the three XP fields
(experience, level_up_available, xp_to_next_level) flow through
the REST and WS transports with correct values at L1.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action

WORLD = "combat_test"
LOCATION = "combat_floor"


def _create_session(api_url: str, player_api_url: str) -> tuple[str, str]:
    resp = requests.post(f"{api_url}/sessions", json={"world_name": WORLD, "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    resp = requests.post(
        f"{player_api_url}/sessions/{sid}/character",
        json={
            "name": "XP Hero",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "start_location": LOCATION,
            "ability_scores": {"str": 15, "dex": 11, "con": 14, "int": 10, "wis": 10, "cha": 9},
        },
        timeout=10,
    )
    resp.raise_for_status()
    return sid, resp.json()["player_id"]


def _get_turn(sock: ws_lib.WebSocket, max_msgs: int = 40) -> dict[str, Any]:
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == "turn":
            return msg
    raise AssertionError("Never received turn message")


def _collect_until_turn(sock: ws_lib.WebSocket, max_msgs: int = 60) -> dict[str, Any]:
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == "turn":
            return msg
    raise AssertionError("Never received next turn message")


class TestPlayerStateXpInitial:
    """L1 character starts with experience=0 and xp_to_next_level=300 (PHB)."""

    def test_rest_status_has_xp_fields_at_level_1(self, api_url: str, player_api_url: str) -> None:
        sid, _pid = _create_session(api_url, player_api_url)
        try:
            resp = requests.get(f"{player_api_url}/sessions/{sid}/status", timeout=10)
            assert resp.status_code == HTTPStatus.OK
            data = resp.json()
            assert data["experience"] == 0
            assert data["level"] == 1
            assert data["level_up_available"] is False
            assert data["xp_to_next_level"] == 300
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=10)

    def test_ws_turn_player_has_xp_fields(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        sid, pid = _create_session(api_url, player_api_url)
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                player = turn["player"]
                assert player["experience"] == 0
                assert player["level"] == 1
                assert player["level_up_available"] is False
                assert player["xp_to_next_level"] == 300
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=10)


class TestPlayerStateXpAfterKill:
    """After killing a creature with xp_value=50, payload reflects new XP totals."""

    def test_rest_status_updated_after_kill(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        sid, pid = _create_session(api_url, player_api_url)
        try:
            # Remove allied NPC so the player gets the kill credit
            requests.delete(f"{api_url}/sessions/{sid}/creatures/ally_fighter_npc", timeout=10).raise_for_status()

            # Give target_dummy a CR-1/4 XP value and 1 HP so one attack kills it
            requests.patch(
                f"{api_url}/sessions/{sid}/creatures/target_dummy",
                json={"current_hp": 1, "xp_value": 50},
                timeout=10,
            ).raise_for_status()

            # Verify patch landed
            dummy = requests.get(f"{api_url}/sessions/{sid}/creatures/target_dummy", timeout=10).json()
            assert dummy["hp"] == 1

            sock = ws_connect(ws_base_url, sid, pid)
            try:
                _get_turn(sock)
                # Attack until we observe an xp_gained event or dummy dies
                ws_send_action(sock, "attack", target_id="target_dummy")
                got_xp_event = False
                for _ in range(20):
                    try:
                        msg = ws_recv(sock)
                    except Exception:
                        break
                    events = msg.get("events", []) if isinstance(msg, dict) else []
                    if any(e.get("event_type") == "xp_gained" for e in events):
                        got_xp_event = True
                        break
                    if msg.get("type") == "turn":
                        dummy = requests.get(f"{api_url}/sessions/{sid}/creatures/target_dummy", timeout=10).json()
                        if dummy["hp"] <= 0:
                            break
                        actions = {a["name"] for a in msg.get("awareness", {}).get("available_actions", [])}
                        if "attack" in actions:
                            ws_send_action(sock, "attack", target_id="target_dummy")

                # Keep socket open so session doesn't get evicted + restored before our GET
                assert got_xp_event, "Expected xp_gained event in perceived events"
                resp = requests.get(f"{player_api_url}/sessions/{sid}/status", timeout=10)
            finally:
                sock.close()

            assert resp.status_code == HTTPStatus.OK
            data = resp.json()
            assert data["experience"] == 50, f"Expected 50 XP after kill, got {data['experience']}"
            assert data["level_up_available"] is False
            assert data["xp_to_next_level"] == 250
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=10)
