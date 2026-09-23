"""Integration test: looting a corpse in combat costs an Action (dnd-simulator-277).

Runs against the live backend in docker compose (DND_DICE_SEED=42) with ``loot_test``:
the player stands at (10, 10); ``loot_weakling`` (1 HP, AC 1, 12 gold and a potion) starts
next to it at (15, 10); ``loot_sentinel`` (speed 0) stands far away at (50, 50) and keeps
the fight going after the weakling dies. The weakling's corpse keeps its last cell, so on
the next combat turn the player loots it from the adjacent cell for its Action.
"""

from __future__ import annotations

from typing import Any

import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action

WORLD = "loot_test"
START = "loot_floor"
WEAKLING = "loot_weakling"


def _create_session(api_url: str, player_api_url: str) -> tuple[str, str]:
    resp = requests.post(f"{api_url}/sessions", json={"world_name": WORLD, "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]
    resp = requests.post(
        f"{player_api_url}/sessions/{sid}/character",
        json={
            "name": "Looter",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "start_location": START,
            "ability_scores": {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8},
            "fighting_style": "defense",
            "combat_position": [10, 10],
        },
        timeout=10,
    )
    resp.raise_for_status()
    return sid, resp.json()["player_id"]


def _next(sock: ws_lib.WebSocket, msg_type: str, max_msgs: int = 80) -> dict[str, Any]:
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == msg_type:
            return msg
    raise AssertionError(f"Never received a {msg_type} message")


def _lootable(msg: dict[str, Any], holder_id: str) -> dict[str, Any] | None:
    return next((lt for lt in msg["awareness"].get("lootables", []) if lt["id"] == holder_id), None)


class TestLootInCombat:
    def test_player_loots_an_adjacent_corpse_for_an_action(
        self, backend_url: str, api_url: str, player_api_url: str
    ) -> None:
        sid, pid = _create_session(api_url, player_api_url)
        sock = ws_connect(backend_url.replace("http://", "ws://") + "/api/ws", sid, pid)
        sock.settimeout(30)
        try:
            # The hostile bandits start the fight on sight. Swing at the weakling until it is a
            # corpse, then wait for a prompt with the Action still unspent (the killing blow
            # itself spends the Action of that turn).
            corpse = None
            for _ in range(20):
                turn = _next(sock, "turn", max_msgs=200)
                assert turn["mode"] == "combat", "the sentinel must keep the fight going"
                corpse = _lootable(turn, WEAKLING)
                has_action = turn["budget"]["actions"] >= 1
                if corpse is not None and has_action:
                    break
                if corpse is None and has_action:
                    ws_send_action(sock, "attack", target_id=WEAKLING)
                else:
                    ws_send_action(sock, "end_turn")
            assert corpse is not None, "the weakling never died"

            # The corpse kept its cell next to the player: in reach, with its loot listed.
            assert corpse["in_reach"] is True
            assert corpse["distance_ft"] <= 5
            assert corpse["loot_gold"] == 12
            assert [i["name"] for i in corpse["loot_items"]] == ["Healing Potion"]
            assert "take" in [a["name"] for a in turn["awareness"]["available_actions"]]
            assert turn["budget"]["actions"] == 1
            gold_before = turn["player"]["gold"]

            ws_send_action(sock, "take", target_id=WEAKLING)
            result = _next(sock, "action_result")

            assert result["actor"] == pid
            assert "error" not in result, result.get("error")
            assert result["mode"] == "combat"
            assert result["budget"]["actions"] == 0  # the Action is actually charged
            assert result["player"]["gold"] == gold_before + 12
            looted = _lootable(result, WEAKLING)
            assert looted is not None and looted["loot_gold"] == 0 and looted["loot_items"] == []

            # Still the player's turn (bonus action, movement left) — but no Action, so no take.
            turn = _next(sock, "turn")
            assert turn["mode"] == "combat"
            assert turn["budget"]["actions"] == 0
            assert "take" not in [a["name"] for a in turn["awareness"]["available_actions"]]

            # A second take in the same turn has no Action left to spend.
            ws_send_action(sock, "take", target_id=WEAKLING)
            result = _next(sock, "action_result")
            assert result["error"].startswith("Not enough budget left this turn: Take all items")
        finally:
            sock.close()
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
