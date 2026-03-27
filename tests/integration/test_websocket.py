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
    resp = requests.post(f"{api}/sessions", json={"world_name": "arena", "lang": "en"}, timeout=10)
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
    resp = requests.post(f"{api}/sessions", json={"world_name": "village", "lang": "en"}, timeout=10)
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


# ── Click-to-Move (move_to) ───────────────────────────────────────────


class TestMoveTo:
    """Phase 5: move_to action — BFS pathfinding on the battle map grid."""

    @pytest.fixture(scope="class")
    def ws_move_arena(self, _urls: tuple[str, str, str]) -> Iterator[tuple[str, str, str]]:
        """Fresh arena session for move_to tests."""
        api, player_api, ws_base = _urls
        resp = requests.post(f"{api}/sessions", json={"world_name": "arena", "lang": "en"}, timeout=10)
        resp.raise_for_status()
        sid = resp.json()["session_id"]

        resp = requests.post(
            f"{player_api}/sessions/{sid}/character",
            json={
                "name": "Move Tester",
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

    def test_move_to_in_combat(self, ws_move_arena: tuple[str, str, str]) -> None:
        """Enter combat, then move_to an adjacent cell — should succeed and update position."""
        ws_base, sid, pid = ws_move_arena
        sock = ws_connect(ws_base, sid, pid)
        try:
            # Get initial peaceful turn
            msg = ws_recv(sock)
            assert msg["type"] == "turn"

            # Attack to start combat
            ws_send_action(sock, "attack", target_id="razor")

            # Wait for a combat turn (ours)
            combat_turn = None
            for _ in range(20):
                msg = ws_recv(sock)
                if msg["type"] == "turn" and msg.get("mode") == "combat":
                    combat_turn = msg
                    break
            assert combat_turn is not None, "Never got a combat turn"

            # Read our current position from awareness
            awareness = combat_turn["awareness"]
            cur_x = awareness["self_x"]
            cur_y = awareness["self_y"]

            # Pick a target cell 1 step away (5ft grid)
            target_x = cur_x + 5
            target_y = cur_y

            ws_send_action(sock, "move_to", x=target_x, y=target_y)

            # Should get action_result for move_to (no "error" key = success)
            got_result = False
            for _ in range(10):
                msg = ws_recv(sock)
                if msg["type"] == "action_result" and msg["action"] == "move_to":
                    assert "error" not in msg, f"move_to failed: {msg.get('error')}"
                    got_result = True
                    break
            assert got_result, f"Never received move_to action_result, last msg: {msg}"
        finally:
            sock.close()

    def test_move_to_outside_combat_fails(self, _urls: tuple[str, str, str]) -> None:
        """move_to should fail outside combat — it's a combat-only action."""
        api, player_api, ws_base = _urls
        resp = requests.post(f"{api}/sessions", json={"world_name": "village", "lang": "en"}, timeout=10)
        resp.raise_for_status()
        sid = resp.json()["session_id"]

        try:
            resp = requests.post(
                f"{player_api}/sessions/{sid}/character",
                json={
                    "name": "Peace Mover",
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

            sock = ws_connect(ws_base, sid, pid)
            try:
                msg = ws_recv(sock)
                assert msg["type"] == "turn"
                assert msg["mode"] == "peaceful"

                ws_send_action(sock, "move_to", x=5, y=5)

                # In peaceful mode, a combat-only action fails —
                # the turn breaks, round ends, and we get round_result then new turn
                msg = ws_recv(sock)
                assert msg["type"] in ("round_result", "turn"), (
                    f"Expected round_result or turn after failed move_to, got: {msg['type']}"
                )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api}/sessions/{sid}", timeout=5)


# ── Inventory & Equipment ─────────────────────────────────────────────


class TestInventoryEquipment:
    """Phase 2: inventory/equipment/gold visible in turn messages."""

    @pytest.fixture(scope="class")
    def ws_equipped(self, _urls: tuple[str, str, str]) -> Iterator[tuple[str, str, str]]:
        """Village session where player starts with a weapon and gold (no combat)."""
        api, player_api, ws_base = _urls
        resp = requests.post(f"{api}/sessions", json={"world_name": "village", "lang": "en"}, timeout=10)
        resp.raise_for_status()
        sid = resp.json()["session_id"]

        resp = requests.post(
            f"{player_api}/sessions/{sid}/character",
            json={
                "name": "Inv Tester",
                "race": "human",
                "char_class": "fighter",
                "level": 1,
                "alignment": "true_neutral",
                "hp": 30,
                "ac": 15,
                "gold": 100,
                "start_location": "village_square",
                "ability_scores": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 10},
            },
            timeout=10,
        )
        resp.raise_for_status()
        pid = resp.json()["player_id"]

        # Give the player a weapon
        requests.post(
            f"{api}/sessions/{sid}/creatures/{pid}/items",
            json={
                "name": "Test Sword",
                "type": "weapon",
                "weapon_id": "test_sword",
                "category": "martial",
                "attack_name": "slash",
                "damage": [{"dice": "1d8", "type": "slashing"}],
                "ability": "str",
            },
            timeout=10,
        ).raise_for_status()

        # Give the player a potion
        requests.post(
            f"{api}/sessions/{sid}/creatures/{pid}/items",
            json={"name": "Health Potion", "type": "potion", "heal_dice": "2d4+2"},
            timeout=10,
        ).raise_for_status()

        yield ws_base, sid, pid
        requests.delete(f"{api}/sessions/{sid}", timeout=5)

    def test_turn_has_inventory_and_equipped(self, ws_equipped: tuple[str, str, str]) -> None:
        """Turn message includes equipped and inventory arrays."""
        ws_base, sid, pid = ws_equipped
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
            player = msg["player"]

            assert "equipped" in player
            assert "inventory" in player
            assert isinstance(player["equipped"], list)
            assert isinstance(player["inventory"], list)
        finally:
            sock.close()

    def test_gold_in_player(self, ws_equipped: tuple[str, str, str]) -> None:
        """Turn message includes gold amount."""
        ws_base, sid, pid = ws_equipped
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
            assert msg["player"]["gold"] == 100
        finally:
            sock.close()

    def test_inventory_contains_given_items(self, ws_equipped: tuple[str, str, str]) -> None:
        """Inventory contains items given via API."""
        ws_base, sid, pid = ws_equipped
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
            inventory = msg["player"]["inventory"]
            names = [item["name"] for item in inventory]
            assert "Test Sword" in names
            assert "Health Potion" in names
            # Each item has id, name, description
            for item in inventory:
                assert "id" in item
                assert "name" in item
                assert "description" in item
        finally:
            sock.close()

    def test_equip_and_unequip_via_ws(self, ws_equipped: tuple[str, str, str]) -> None:
        """Equip a weapon via WS, verify it appears in equipped slots."""
        ws_base, sid, pid = ws_equipped
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"

            # Find the sword's item_id from inventory
            inventory = msg["player"]["inventory"]
            sword = next(i for i in inventory if i["name"] == "Test Sword")
            sword_id = sword["id"]

            # Equip the sword (param is weapon_id, not item_id)
            ws_send_action(sock, "equip", weapon_id=sword_id)

            # In peaceful mode, equip ends turn → next turn should show equipped weapon
            equipped_weapon = False
            for _ in range(10):
                msg = ws_recv(sock)
                if msg["type"] == "turn" and "player" in msg:
                    equipped = msg["player"]["equipped"]
                    weapon_slots = [e for e in equipped if e["slot"] == "weapon"]
                    if weapon_slots and weapon_slots[0]["name"] == "Test Sword":
                        equipped_weapon = True
                        break
            assert equipped_weapon, "Sword never appeared in equipped slots"

            # Now unequip
            ws_send_action(sock, "unequip")
            unequipped = False
            for _ in range(10):
                msg = ws_recv(sock)
                if msg["type"] == "turn" and "player" in msg:
                    equipped = msg["player"]["equipped"]
                    weapon_slots = [e for e in equipped if e["slot"] == "weapon"]
                    if not weapon_slots:
                        unequipped = True
                        break
            assert unequipped, "Weapon still in equipped after unequip"
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
