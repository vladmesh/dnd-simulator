"""Integration tests: flee leaves the fight and the scene along one edge (dnd-simulator-275).

Runs against the live backend in docker compose (DND_DICE_SEED=42) with ``encounter_world``:
``border_post`` has no encounter table and two neighbours — ``wild_trail`` (500 m, regional
goblin table with chance 1.0) and ``night_marsh``. ``wild_den`` is not adjacent to it.

The player starts at ``border_post`` at (0, 0); two GM-spawned brutes stand far away, so a
three-participant fight starts when the player attacks and the flee is allowed.
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
            "name": "Runner",
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
    for brute_id, position in (("brute_a", [55, 55]), ("brute_b", [55, 45])):
        resp = requests.post(
            f"{api_url}/sessions/{sid}/creatures",
            json={
                "id": brute_id,
                "name": "Brute",
                "entity_type": "monster",
                "start_location": START,
                "hp": 40,
                "ac": 12,
                "speed": 30,
                "combat_position": position,
            },
            timeout=10,
        )
        resp.raise_for_status()
    return sid, pid


def _next(sock: ws_lib.WebSocket, msg_type: str, max_msgs: int = 60) -> dict[str, Any]:
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == msg_type:
            return msg
    raise AssertionError(f"Never received a {msg_type} message")


def _creatures_at(api_url: str, sid: str, location_id: str) -> list[dict[str, Any]]:
    resp = requests.get(f"{api_url}/sessions/{sid}/creatures", params={"location_id": location_id}, timeout=5)
    resp.raise_for_status()
    return list(resp.json())


def _enter_combat(sock: ws_lib.WebSocket) -> dict[str, Any]:
    turn = _next(sock, "turn")
    assert turn["mode"] == "peaceful"
    ws_send_action(sock, "attack", target_id="brute_a")
    for _ in range(60):
        msg = ws_recv(sock)
        if msg["type"] == "turn" and msg["mode"] == "combat":
            return msg
    raise AssertionError("Never entered combat")


class TestPlayerFlee:
    def test_flee_payload_rejections_and_journey(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        sid, pid = _create_session(api_url, player_api_url)
        sock = ws_connect(backend_url.replace("http://", "ws://") + "/api/ws", sid, pid)
        sock.settimeout(30)
        try:
            turn = _enter_combat(sock)

            # (1) The combat turn tells the UI whether flee is allowed and where it leads.
            flee = turn["awareness"]["flee"]
            assert flee["allowed"] is True
            assert flee["reason_key"] is None
            destinations = {d["id"]: d for d in flee["destinations"]}
            assert set(destinations) == {"wild_trail", "night_marsh"}
            assert destinations["wild_trail"]["name"] == "Wild Trail"
            assert destinations["wild_trail"]["travel_seconds"] > 0
            assert "flee" in [a["name"] for a in turn["awareness"]["available_actions"]]

            # (2) No destination / a non-adjacent one is rejected; the player stays in the fight.
            for params, error in (
                ({}, "Choose a neighbouring location to flee to"),
                ({"destination_id": "wild_den"}, "You can only flee to a neighbouring location"),
            ):
                ws_send_action(sock, "flee", **params)
                result = _next(sock, "action_result")
                assert result["error"] == error
                turn = _next(sock, "turn")
                assert turn["mode"] == "combat"

            # (3) A legal flee: out of the fight, on the road to the chosen neighbour.
            ws_send_action(sock, "flee", destination_id="wild_trail")
            result = _next(sock, "action_result")
            assert "error" not in result
            assert result["mode"] == "peaceful"
            turn = _next(sock, "turn")
            journey = turn["player"]["journey"]
            assert journey["destination_id"] == "wild_trail"
            assert [a["name"] for a in turn["awareness"]["available_actions"]] == ["travel"]
            ws_send_action(sock, "end_turn")

            # (4) Travel time passes, the player arrives and the regional table is rolled.
            for _ in range(2000):
                msg = ws_recv(sock)
                if msg["type"] == "turn" and msg["location"].get("current_location_id") == "wild_trail":
                    break
            else:
                raise AssertionError("Player never arrived at wild_trail")
            assert msg["mode"] == "peaceful"
            # As for ordinary travel, the arrival is rolled on the activation pass after the
            # arrival one (the traveller was dormant on the road until then).
            for _ in range(3):
                at_trail = _creatures_at(api_url, sid, "wild_trail")
                if any(c["name"] == "Goblin" for c in at_trail):
                    break
                ws_send_action(sock, "end_turn")
                _next(sock, "turn", max_msgs=200)
            assert any(c["name"] == "Goblin" for c in at_trail)
            assert not any(c["id"] in ("brute_a", "brute_b") for c in at_trail)  # nobody followed
            assert not any(c["id"] == pid for c in _creatures_at(api_url, sid, START))
        finally:
            sock.close()
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
