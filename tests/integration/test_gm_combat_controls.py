"""Integration tests: GM delete / kill of a creature in an active combat (issue ae4bde95c6d2043858d0).

Runs against the live backend in docker compose (DND_DICE_SEED=42) with ``encounter_world``:
``border_post`` has no encounter table. The player starts there at (0, 0) and two slow
GM-spawned brutes join the fight the player starts. While the player's combat turn waits for
input, the GM deletes one brute and zeroes the other's HP; the fight must end without any
further attack.
"""

from __future__ import annotations

from typing import Any

import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action

WORLD = "encounter_world"
START = "border_post"


def _create_session(api_url: str, player_api_url: str) -> tuple[str, str]:
    resp = requests.post(f"{api_url}/sessions", json={"world_name": WORLD, "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]
    resp = requests.post(
        f"{player_api_url}/sessions/{sid}/character",
        json={
            "name": "Warden",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "start_location": START,
            "ability_scores": {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8},
            "fighting_style": "defense",
            "combat_position": [0, 0],
        },
        timeout=10,
    )
    resp.raise_for_status()
    pid = resp.json()["player_id"]
    for brute_id in ("brute_a", "brute_b"):
        resp = requests.post(
            f"{api_url}/sessions/{sid}/creatures",
            json={
                "id": brute_id,
                "name": "Brute",
                "entity_type": "monster",
                "start_location": START,
                "hp": 40,
                "ac": 12,
                "speed": 10,
            },
            timeout=10,
        )
        resp.raise_for_status()
    return sid, pid


def _next_turn(sock: ws_lib.WebSocket, max_msgs: int = 60) -> dict[str, Any]:
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == "turn":
            return msg
    raise AssertionError("Never received a turn message")


def _enter_combat(sock: ws_lib.WebSocket) -> dict[str, Any]:
    turn = _next_turn(sock)
    assert turn["mode"] == "peaceful"
    ws_send_action(sock, "attack", target_id="brute_a")
    for _ in range(60):
        msg = ws_recv(sock)
        if msg["type"] == "turn" and msg["mode"] == "combat":
            return msg
    raise AssertionError("Never entered combat")


class TestGmControlsInCombat:
    def test_gm_delete_then_kill_last_enemy_ends_combat(
        self, backend_url: str, api_url: str, player_api_url: str
    ) -> None:
        sid, pid = _create_session(api_url, player_api_url)
        sock = ws_connect(backend_url.replace("http://", "ws://") + "/api/ws", sid, pid)
        sock.settimeout(30)
        try:
            turn = _enter_combat(sock)
            assert {e["id"] for e in turn["awareness"]["nearby"]} >= {"brute_a", "brute_b"}

            # (1) GM delete: the brute leaves the world and the fight (no ghost in initiative / on the map).
            resp = requests.delete(f"{api_url}/sessions/{sid}/creatures/brute_b", timeout=5)
            assert resp.status_code == 200
            ws_send_action(sock, "end_turn")
            turn = _next_turn(sock, max_msgs=200)
            assert turn["mode"] == "combat"
            assert "brute_b" not in {e["id"] for e in turn["awareness"]["nearby"]}
            assert "brute_a" in {e["id"] for e in turn["awareness"]["nearby"]}
            assert len(turn["awareness"]["occupied_cells"]) == 1  # only brute_a's cell; brute_b's cell is free

            # (2) GM kill of the last enemy: the normal death path ends the fight.
            resp = requests.patch(f"{api_url}/sessions/{sid}/creatures/brute_a", json={"current_hp": 0}, timeout=5)
            assert resp.status_code == 200
            ws_send_action(sock, "end_turn")
            turn = _next_turn(sock, max_msgs=200)
            assert turn["mode"] == "peaceful"

            creatures = {c["id"]: c for c in requests.get(f"{api_url}/sessions/{sid}/creatures", timeout=5).json()}
            assert "brute_b" not in creatures
            assert creatures["brute_a"]["hp"] == 0  # the corpse stays in the world
        finally:
            sock.close()
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
