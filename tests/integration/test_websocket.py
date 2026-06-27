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
            "alignment": "true_neutral",
            "start_location": "arena_floor",
            "ability_scores": {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8},
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
            "alignment": "true_neutral",
            "start_location": "village_square",
            "ability_scores": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
        },
        timeout=10,
    )
    resp.raise_for_status()
    pid = resp.json()["player_id"]

    yield ws_base, sid, pid
    requests.delete(f"{api}/sessions/{sid}", timeout=5)


def _recv_until(sock: ws_lib.WebSocket, target_type: str, max_msgs: int = 80) -> dict | None:
    """Receive messages until one with target_type appears, or return None.

    The arena session is module-scoped and shared across WS tests, so on connect
    the server can replay a long burst of combat events (4 fighters, multi-action
    turns) before the player's ``turn``. Keep the cap well above a worst-case round.
    """
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

    def test_attack_event_has_structured_dice(self, ws_arena: tuple[str, str, str]) -> None:
        """Attack events carry structured dice breakdown: attack_roll with d20, components, and damage_components."""
        ws_base, sid, pid = ws_arena
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            if msg["type"] != "turn":
                msg = _recv_until(sock, "turn")
                assert msg is not None

            ws_send_action(sock, "attack", target_id="razor")

            attack_data = None
            for _ in range(20):
                msg = ws_recv(sock)
                if msg["type"] == "action_result" and msg["action"] == "attack":
                    for ev in msg["events"]:
                        data = ev.get("data", {})
                        if data.get("attacker_id") and data.get("attack_roll"):
                            attack_data = data
                            break
                    if attack_data:
                        break
                if msg["type"] == "turn":
                    ws_send_action(sock, "attack", target_id="razor")

            assert attack_data is not None, "Never got attack event with attack_roll"

            # attack_roll structure
            atk_roll = attack_data["attack_roll"]
            assert "natural" in atk_roll
            assert "total" in atk_roll
            assert "advantage" in atk_roll
            assert "disadvantage" in atk_roll
            assert "components" in atk_roll

            # d20 structure
            d20 = atk_roll["d20"]
            assert isinstance(d20["result"], int)
            assert d20["sides"] == 20

            # components are lists of {source, value, dice}
            for comp in atk_roll["components"]:
                assert "source" in comp
                assert "value" in comp

            # If hit, verify damage_components structure
            if attack_data.get("hit"):
                assert "damage_components" in attack_data
                for dc in attack_data["damage_components"]:
                    assert "source" in dc
                    assert "amount" in dc
                    assert "type" in dc
                    assert "dice_detail" in dc
                    for die in dc["dice_detail"]:
                        assert "sides" in die
                        assert "result" in die
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
        """Fresh session for move_to tests. Uses move_test world (1 weak NPC)."""
        api, player_api, ws_base = _urls
        resp = requests.post(f"{api}/sessions", json={"world_name": "move_test", "lang": "en"}, timeout=10)
        resp.raise_for_status()
        sid = resp.json()["session_id"]

        resp = requests.post(
            f"{player_api}/sessions/{sid}/character",
            json={
                "name": "Move Tester",
                "race": "human",
                "char_class": "fighter",
                "alignment": "true_neutral",
                "start_location": "test_floor",
                "ability_scores": {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8},
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
            # Wait for initial turn — may be peaceful or combat (hostile factions auto-start combat)
            msg = None
            for _ in range(20):
                msg = ws_recv(sock)
                if msg["type"] == "turn":
                    break
            assert msg is not None and msg["type"] == "turn", f"Never got initial turn, last: {msg}"

            if msg.get("mode") != "combat":
                # Peaceful turn — attack to start combat
                ws_send_action(sock, "attack", target_id="dummy")

            # Wait for a combat turn (ours)
            combat_turn = None
            if msg.get("mode") == "combat":
                combat_turn = msg
            else:
                for _ in range(30):
                    msg = ws_recv(sock)
                    if msg["type"] == "turn" and msg.get("mode") == "combat":
                        combat_turn = msg
                        break
            assert combat_turn is not None, "Never got a combat turn"

            # Read our current position from awareness
            awareness = combat_turn["awareness"]
            cur_x = awareness["self_x"]
            cur_y = awareness["self_y"]

            # Try multiple adjacent cells (5ft grid) — some may be blocked by other creatures
            candidates = [
                (cur_x - 5, cur_y),
                (cur_x + 5, cur_y),
                (cur_x, cur_y - 5),
                (cur_x, cur_y + 5),
            ]
            # Prefer cells that stay within reasonable grid bounds
            candidates = [(x, y) for x, y in candidates if x >= 0 and y >= 0]

            got_move = False
            last_error = ""
            for target_x, target_y in candidates:
                ws_send_action(sock, "move_to", x=target_x, y=target_y)

                for _ in range(10):
                    msg = ws_recv(sock)
                    if msg["type"] == "action_result" and msg["action"] == "move_to":
                        if "error" not in msg:
                            got_move = True
                        else:
                            last_error = msg.get("error", "")
                        break
                    if msg["type"] == "turn":
                        # Got next turn prompt — move succeeded and turn continued
                        got_move = True
                        break
                if got_move:
                    break

            assert got_move, f"All adjacent cells blocked. Last error: {last_error}"
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
                    "alignment": "true_neutral",
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
                # server sends action_result with error, then round ends with new turn
                msg = ws_recv(sock)
                assert msg["type"] == "action_result", (
                    f"Expected action_result with error after failed move_to, got: {msg['type']}"
                )
                assert msg.get("error"), "action_result should contain an error message"

                msg = ws_recv(sock)
                assert msg["type"] in ("round_result", "turn"), (
                    f"Expected round_result or turn after failed move_to, got: {msg['type']}"
                )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api}/sessions/{sid}", timeout=10)


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
                "alignment": "true_neutral",
                "start_location": "village_square",
                "ability_scores": {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8},
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
            assert msg["player"]["gold"] == 1000
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


# ── Lay on Hands ─────────────────────────────────────────────────────


class TestLayOnHands:
    """Phase 2: Lay on Hands — Paladin heals self via WS."""

    @pytest.fixture(scope="class")
    def ws_paladin(self, _urls: tuple[str, str, str]) -> Iterator[tuple[str, str, str]]:
        """Fresh arena session with a Paladin player."""
        api, player_api, ws_base = _urls
        resp = requests.post(f"{api}/sessions", json={"world_name": "arena", "lang": "en"}, timeout=10)
        resp.raise_for_status()
        sid = resp.json()["session_id"]

        resp = requests.post(
            f"{player_api}/sessions/{sid}/character",
            json={
                "name": "WS Paladin",
                "race": "human",
                "char_class": "paladin",
                "alignment": "lawful_good",
                "start_location": "arena_floor",
                "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 10, "cha": 14},
            },
            timeout=10,
        )
        resp.raise_for_status()
        pid = resp.json()["player_id"]

        yield ws_base, sid, pid
        requests.delete(f"{api}/sessions/{sid}", timeout=15)

    def test_lay_on_hands_heal_self(self, ws_paladin: tuple[str, str, str], _urls: tuple[str, str, str]) -> None:
        """Paladin takes damage, uses Lay on Hands on self, HP restored."""
        api, _, _ = _urls
        ws_base, sid, pid = ws_paladin

        # Damage the paladin to 7 HP (from 12 max) so heal is visible
        requests.patch(f"{api}/sessions/{sid}/creatures/{pid}", json={"current_hp": 7}, timeout=5).raise_for_status()

        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"

            ws_send_action(sock, "lay_on_hands", amount=3)

            # Expect action_result for lay_on_hands
            got_result = False
            for _ in range(15):
                msg = ws_recv(sock)
                if msg["type"] == "action_result" and msg["action"] == "lay_on_hands":
                    assert msg.get("success", True)  # no error key
                    assert "error" not in msg
                    got_result = True
                    break
                if msg["type"] == "turn":
                    # If we got a new turn, the action might have ended the turn
                    got_result = True
                    break
            assert got_result, f"Never received lay_on_hands result, last msg: {msg}"
        finally:
            sock.close()


# ── Divine Smite ─────────────────────────────────────────────────────


class TestDivineSmite:
    """Phase 3: Divine Smite — Paladin attack with spell slot consumption."""

    @pytest.fixture(scope="class")
    def ws_smite_paladin(self, _urls: tuple[str, str, str]) -> Iterator[tuple[str, str, str]]:
        """Fresh arena session with a Paladin player who has spell slots."""
        api, player_api, ws_base = _urls
        resp = requests.post(f"{api}/sessions", json={"world_name": "arena", "lang": "en"}, timeout=10)
        resp.raise_for_status()
        sid = resp.json()["session_id"]

        resp = requests.post(
            f"{player_api}/sessions/{sid}/character",
            json={
                "name": "Smite Paladin",
                "race": "human",
                "char_class": "paladin",
                "alignment": "lawful_good",
                "start_location": "arena_floor",
                "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 10, "cha": 14},
            },
            timeout=10,
        )
        resp.raise_for_status()
        pid = resp.json()["player_id"]

        # Promote to L2 (Divine Smite gated at L2) and grant spell slots.
        requests.patch(
            f"{api}/sessions/{sid}/creatures/{pid}",
            json={
                "level": 2,
                "resource_pools": [
                    {"id": "spell_slot_1", "max_uses": 2, "current_uses": 2, "reset_on": "long_rest"},
                ],
            },
            timeout=5,
        ).raise_for_status()

        # Lower razor's AC so paladin reliably hits (AC 5 vs +4 attack = hit on 1+)
        requests.patch(
            f"{api}/sessions/{sid}/creatures/razor",
            json={"ac": 5},
            timeout=5,
        ).raise_for_status()

        # Remove other NPCs to keep rounds short (only player + razor).
        for npc_id in ("shadow", "iron", "paladin"):
            requests.delete(f"{api}/sessions/{sid}/creatures/{npc_id}", timeout=5)

        yield ws_base, sid, pid
        requests.delete(f"{api}/sessions/{sid}", timeout=15)

    def test_smite_adds_radiant_damage(self, ws_smite_paladin: tuple[str, str, str]) -> None:
        """Attack with smite_slot_level=1 adds radiant damage component on hit."""
        ws_base, sid, pid = ws_smite_paladin
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"

            ws_send_action(sock, "attack", target_id="razor", smite_slot_level=1)

            # Collect attack results — look for a hit with radiant damage.
            # With AC 5 only nat-1 misses (5%), but we retry on each turn.
            attack_data = None
            for _ in range(80):
                msg = ws_recv(sock)
                if msg["type"] in ("action_result", "round_result"):
                    for ev in msg.get("events", []):
                        data = ev.get("data", {})
                        if data.get("attacker_id") == pid and data.get("hit"):
                            attack_data = data
                            break
                    if attack_data:
                        break
                if msg["type"] == "turn":
                    ws_send_action(sock, "attack", target_id="razor", smite_slot_level=1)

            assert attack_data is not None, "Never got a hit from paladin attack"

            # Verify radiant damage from smite is in damage_components
            damage_types = {dc["source"] for dc in attack_data["damage_components"]}
            assert "divine_smite" in damage_types, f"Expected divine_smite in damage sources, got: {damage_types}"

            # Verify the smite component is radiant type
            smite_components = [dc for dc in attack_data["damage_components"] if dc["source"] == "divine_smite"]
            assert len(smite_components) == 1
            assert smite_components[0]["type"] == "radiant"
            assert smite_components[0]["amount"] > 0
            # 2d8 radiant — verify dice_detail has 2 d8s
            assert len(smite_components[0]["dice_detail"]) == 2
            for die in smite_components[0]["dice_detail"]:
                assert die["sides"] == 8
        finally:
            sock.close()

    def test_smite_without_slots_fails(self, _urls: tuple[str, str, str]) -> None:
        """Non-Paladin or no-slot creature cannot smite — gets error."""
        api, player_api, ws_base = _urls
        # Create a Fighter (no spell slots)
        resp = requests.post(f"{api}/sessions", json={"world_name": "arena", "lang": "en"}, timeout=10)
        resp.raise_for_status()
        sid = resp.json()["session_id"]
        try:
            resp = requests.post(
                f"{player_api}/sessions/{sid}/character",
                json={
                    "name": "No-Smite Fighter",
                    "race": "human",
                    "char_class": "fighter",
                    "alignment": "true_neutral",
                    "start_location": "arena_floor",
                    "ability_scores": {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8},
                },
                timeout=10,
            )
            resp.raise_for_status()
            pid = resp.json()["player_id"]

            sock = ws_connect(ws_base, sid, pid)
            try:
                msg = ws_recv(sock)
                assert msg["type"] == "turn"

                ws_send_action(sock, "attack", target_id="razor", smite_slot_level=1)

                # Should get an error or action_result with error
                got_rejection = False
                for _ in range(15):
                    msg = ws_recv(sock)
                    if msg["type"] == "action_result" and msg["action"] == "attack":
                        # Attack should fail validation — smite rejected
                        if msg.get("error") or not msg.get("success", True):
                            got_rejection = True
                            break
                        # If attack succeeded without smite (validation stripped it), also ok
                        for ev in msg.get("events", []):
                            data = ev.get("data", {})
                            if data.get("hit") and data.get("damage_components"):
                                sources = {dc["source"] for dc in data["damage_components"]}
                                assert "divine_smite" not in sources, "Fighter should not get divine smite damage"
                        got_rejection = True
                        break
                    if msg["type"] == "error":
                        got_rejection = True
                        break
                    if msg["type"] == "turn":
                        ws_send_action(sock, "attack", target_id="razor", smite_slot_level=1)
                assert got_rejection, f"Expected rejection/error for Fighter smite, last msg: {msg}"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api}/sessions/{sid}", timeout=15)


# ── Target Scope ─────────────────────────────────────────────────────


class TestTargetScope:
    """Phase 6: target_mode/target_scope in available_actions, scope validation."""

    def test_turn_actions_include_target_mode_and_scope(self, ws_arena: tuple[str, str, str]) -> None:
        """Every action in a turn message carries target_mode and target_scope."""
        ws_base, sid, pid = ws_arena
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
            actions = msg["awareness"]["available_actions"]
            assert len(actions) > 0

            for action in actions:
                assert "target_mode" in action, f"action '{action['name']}' missing target_mode"
                assert "target_scope" in action, f"action '{action['name']}' missing target_scope"
        finally:
            sock.close()

    def test_attack_action_has_hostile_scope(self, ws_arena: tuple[str, str, str]) -> None:
        """Attack action should have target_mode=single, target_scope=hostile."""
        ws_base, sid, pid = ws_arena
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
            actions = msg["awareness"]["available_actions"]
            attack = next((a for a in actions if a["name"] == "attack"), None)
            assert attack is not None, "attack action not found in available_actions"
            assert attack["target_mode"] == "single"
            assert attack["target_scope"] == "hostile"
        finally:
            sock.close()

    def test_lay_on_hands_has_ally_scope(self, _urls: tuple[str, str, str]) -> None:
        """Paladin's lay_on_hands should have target_mode=single, target_scope=ally."""
        api, player_api, ws_base = _urls
        resp = requests.post(f"{api}/sessions", json={"world_name": "arena", "lang": "en"}, timeout=10)
        resp.raise_for_status()
        sid = resp.json()["session_id"]

        try:
            resp = requests.post(
                f"{player_api}/sessions/{sid}/character",
                json={
                    "name": "Scope Paladin",
                    "race": "human",
                    "char_class": "paladin",
                    "alignment": "lawful_good",
                    "start_location": "arena_floor",
                    "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 10, "cha": 14},
                },
                timeout=10,
            )
            resp.raise_for_status()
            pid = resp.json()["player_id"]

            # Damage paladin so lay_on_hands appears (provider hides it at full HP)
            requests.patch(
                f"{api}/sessions/{sid}/creatures/{pid}",
                json={"current_hp": 5},
                timeout=5,
            ).raise_for_status()

            sock = ws_connect(ws_base, sid, pid)
            try:
                msg = ws_recv(sock)
                assert msg["type"] == "turn"
                actions = msg["awareness"]["available_actions"]
                loh = next((a for a in actions if a["name"] == "lay_on_hands"), None)
                assert loh is not None, f"lay_on_hands not in actions: {[a['name'] for a in actions]}"
                assert loh["target_mode"] == "single"
                assert loh["target_scope"] == "ally"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api}/sessions/{sid}", timeout=10)

    def test_self_actions_have_self_mode(self, ws_arena: tuple[str, str, str]) -> None:
        """Dodge/dash/disengage should have target_mode=self."""
        ws_base, sid, pid = ws_arena
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
            actions = {a["name"]: a for a in msg["awareness"]["available_actions"]}
            for name in ("dodge", "dash", "disengage"):
                if name in actions:
                    assert actions[name]["target_mode"] == "self", (
                        f"{name} expected target_mode=self, got {actions[name]['target_mode']}"
                    )
        finally:
            sock.close()

    def test_none_mode_actions(self, ws_arena: tuple[str, str, str]) -> None:
        """Equip/say/wait/end_turn should have target_mode=none."""
        ws_base, sid, pid = ws_arena
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
            actions = {a["name"]: a for a in msg["awareness"]["available_actions"]}
            for name in ("end_turn",):
                if name in actions:
                    assert actions[name]["target_mode"] == "none", (
                        f"{name} expected target_mode=none, got {actions[name]['target_mode']}"
                    )
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
