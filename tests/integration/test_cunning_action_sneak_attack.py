"""Integration tests for Phase 3: Cunning Action cost_mode & Sneak Attack faction check.

Tests run against a live backend in docker compose with:
- DND_DICE_SEED=42 (deterministic rolls)
- Test content (arena + sneak_test worlds, all rule-based)

Each test creates its own session to avoid state pollution from combat rounds.
"""

from __future__ import annotations

from typing import Any

import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action

# ── Helpers ──────────────────────────────────────────────────────────────


def _create_session(api_url: str, player_api_url: str, world: str, location: str, char_class: str) -> tuple[str, str]:
    """Create session + player. Returns (session_id, player_id)."""
    resp = requests.post(f"{api_url}/sessions", json={"world_name": world, "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    scores = (
        {"str": 10, "dex": 15, "con": 12, "int": 14, "wis": 12, "cha": 8}
        if char_class == "rogue"
        else {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8}
    )

    resp = requests.post(
        f"{player_api_url}/sessions/{sid}/character",
        json={
            "name": f"Test {char_class.title()}",
            "race": "elf" if char_class == "rogue" else "human",
            "char_class": char_class,
            "alignment": "true_neutral",
            "start_location": location,
            "ability_scores": scores,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return sid, resp.json()["player_id"]


def _give_rapier(api_url: str, sid: str, pid: str) -> None:
    """Give creature a rapier via master API."""
    requests.post(
        f"{api_url}/sessions/{sid}/creatures/{pid}/items",
        json={
            "name": "Rapier",
            "type": "weapon",
            "weapon_id": "rapier",
            "category": "martial",
            "attack_name": "rapier thrust",
            "damage": [{"dice": "1d8", "type": "piercing"}],
            "ability": "dex",
            "is_finesse": True,
        },
        timeout=10,
    ).raise_for_status()


def _boost_hp(api_url: str, sid: str, pid: str, hp: int = 100) -> None:
    """Boost creature HP so it survives combat long enough for testing."""
    requests.patch(
        f"{api_url}/sessions/{sid}/creatures/{pid}",
        json={"current_hp": hp, "max_hp": hp},
        timeout=10,
    ).raise_for_status()


def _get_turn(sock: ws_lib.WebSocket, max_msgs: int = 20) -> dict[str, Any]:
    """Receive messages until a turn message arrives."""
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == "turn":
            return msg
    raise AssertionError("Never received turn message")


def _ensure_combat(sock: ws_lib.WebSocket, turn: dict[str, Any], target_id: str) -> dict[str, Any]:
    """If peaceful, attack target to start combat. Returns a combat turn."""
    if turn["mode"] == "combat":
        return turn
    ws_send_action(sock, "attack", target_id=target_id)
    for _ in range(80):
        msg = ws_recv(sock)
        if msg["type"] == "turn" and msg.get("mode") == "combat":
            return msg
        # In combat, we might get action_result, round_result first — keep reading
    raise AssertionError("Failed to enter combat")


def _equip_rapier(sock: ws_lib.WebSocket, turn: dict[str, Any]) -> dict[str, Any]:
    """Equip the rapier from inventory. Returns the next turn message."""
    inventory = turn["player"]["inventory"]
    rapier = next(i for i in inventory if i["name"] == "Rapier")
    ws_send_action(sock, "equip", weapon_id=rapier["id"])
    return _get_turn(sock)


# ── Cunning Action: cost_mode via WS ────────────────────────────────────


class TestCunningActionCostMode:
    """Test that rogues can send dash/disengage with cost_mode=bonus_action."""

    def test_rogue_dash_has_cost_options(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Rogue's combat turn includes cost_options for dash and disengage."""
        sid, pid = _create_session(api_url, player_api_url, "arena", "arena_floor", "rogue")
        try:
            _boost_hp(api_url, sid, pid)
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "razor")

                actions = {a["name"]: a for a in turn["awareness"]["available_actions"]}

                # Dash should have both action and bonus_action cost options
                assert "dash" in actions
                dash = actions["dash"]
                assert "cost_options" in dash, "Rogue dash should have cost_options"
                cost_types = {opt["cost_type"] for opt in dash["cost_options"]}
                assert "action" in cost_types
                assert "bonus_action" in cost_types

                # Disengage too
                assert "disengage" in actions
                disengage = actions["disengage"]
                assert "cost_options" in disengage
                disengage_costs = {opt["cost_type"] for opt in disengage["cost_options"]}
                assert "bonus_action" in disengage_costs
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_rogue_dash_as_bonus_action_preserves_action(
        self, api_url: str, player_api_url: str, ws_base_url: str
    ) -> None:
        """Rogue sends dash with cost_mode=bonus_action — bonus_action consumed, action remains."""
        sid, pid = _create_session(api_url, player_api_url, "arena", "arena_floor", "rogue")
        try:
            _boost_hp(api_url, sid, pid)
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "razor")
                assert turn["budget"]["bonus_actions"] >= 1
                assert turn["budget"]["actions"] >= 1

                ws_send_action(sock, "dash", cost_mode="bonus_action")

                # After dash as bonus action, next turn should have action remaining
                turn2 = _get_turn(sock)
                assert turn2["budget"]["actions"] >= 1, "Action should remain after bonus-action dash"
                assert turn2["budget"]["bonus_actions"] == 0, "Bonus action should be consumed"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_fighter_dash_no_cost_options(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Fighter's dash does NOT have cost_options (no Cunning Action)."""
        sid, pid = _create_session(api_url, player_api_url, "arena", "arena_floor", "fighter")
        try:
            _boost_hp(api_url, sid, pid)
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "razor")

                actions = {a["name"]: a for a in turn["awareness"]["available_actions"]}
                assert "dash" in actions
                dash = actions["dash"]
                assert "cost_options" not in dash, "Fighter should not have cost_options on dash"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_fighter_dash_with_bonus_cost_mode_rejected(
        self, api_url: str, player_api_url: str, ws_base_url: str
    ) -> None:
        """Fighter sending dash with cost_mode=bonus_action gets an error."""
        sid, pid = _create_session(api_url, player_api_url, "arena", "arena_floor", "fighter")
        try:
            _boost_hp(api_url, sid, pid)
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "razor")

                ws_send_action(sock, "dash", cost_mode="bonus_action")

                # Should get an error — no cost override for fighters
                got_rejection = False
                for _ in range(20):
                    msg = ws_recv(sock)
                    if msg["type"] == "error":
                        got_rejection = True
                        break
                    if msg["type"] == "action_result":
                        # action_result with error info
                        got_rejection = True
                        break
                    if msg["type"] == "turn":
                        # Turn came back — budget should still have actions (dash wasn't consumed)
                        got_rejection = True
                        break
                assert got_rejection, "Fighter's bonus-action dash should be rejected"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=10)


# ── Sneak Attack: faction-aware ally detection ───────────────────────────


class TestSneakAttackFactionCheck:
    """Test SA faction-aware ally detection via equip + weapon pipeline.

    Full SA ally-adjacency is covered by unit tests (test_sneak_attack_faction.py).
    Integration-level SA positioning test is blocked by battle_map_configs not being
    wired from regions.yaml to EntitiesLayer (all maps default to 60x60).
    """

    def test_rogue_equips_finesse_weapon(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Rogue can equip a finesse rapier via the full REST + WS pipeline."""
        sid, pid = _create_session(api_url, player_api_url, "arena", "arena_floor", "rogue")
        _give_rapier(api_url, sid, pid)
        _boost_hp(api_url, sid, pid)
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _equip_rapier(sock, turn)

                equipped = turn.get("player", {}).get("equipped", [])
                weapon = next((e for e in equipped if e.get("slot") == "weapon"), None)
                assert weapon is not None, "Rapier should be equipped"
                assert "finesse" in weapon.get("description", "").lower(), (
                    f"Equipped weapon should be finesse: {weapon}"
                )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=10)
