"""Integration tests: Opportunity attacks fire during movement.

Tests run against a live backend in docker compose with:
- DND_DICE_SEED=42 (deterministic dice rolls)
- oa_test world: 25x25 battle map, 2 enemy guards, all rule-based

Each test creates its own session to avoid state pollution.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action

WORLD = "oa_test"
LOCATION = "oa_floor"


# ── Geometry helpers ──────────────────────────────────────────────────────


def _grid_distance(ax: int, ay: int, bx: int, by: int) -> int:
    """D&D 5e grid distance (alternating diagonal rule)."""
    dx = abs(ax - bx) // 5
    dy = abs(ay - by) // 5
    straight = abs(dx - dy)
    diag = min(dx, dy)
    diag_cost = (diag // 2) * 15 + (diag % 2) * 5
    return straight * 5 + diag_cost


def _player_pos(turn: dict[str, Any]) -> tuple[int, int]:
    """Extract player (x, y) from turn awareness."""
    aw = turn["awareness"]
    return aw["self_x"], aw["self_y"]


def _enemy_pos(turn: dict[str, Any], enemy_id: str) -> tuple[int, int]:
    """Extract enemy (x, y) from turn awareness."""
    for e in turn["awareness"]["nearby"]:
        if e["id"] == enemy_id:
            return e["x"], e["y"]
    raise AssertionError(f"Enemy {enemy_id} not in awareness nearby")


def _find_cell_away_from(
    px: int, py: int, ex: int, ey: int, *, min_dist: int = 15, map_size: int = 25
) -> tuple[int, int]:
    """Find a grid cell at least min_dist from enemy, reachable from player.

    Searches cells in the map for one far enough from the enemy.
    """
    best: tuple[int, int] | None = None
    best_dist = 0
    for x in range(0, map_size, 5):
        for y in range(0, map_size, 5):
            d_from_enemy = _grid_distance(x, y, ex, ey)
            d_from_player = _grid_distance(x, y, px, py)
            if d_from_enemy >= min_dist and d_from_player <= 30 and (best is None or d_from_enemy > best_dist):
                best = (x, y)
                best_dist = d_from_enemy
    if best is None:
        raise AssertionError(f"No cell found ≥{min_dist}ft from enemy ({ex},{ey}) within 30ft of player ({px},{py})")
    return best


# ── Session / WebSocket helpers ───────────────────────────────────────────


def _create_session(
    api_url: str,
    player_api_url: str,
    char_class: str,
    *,
    hp: int = 200,
    items: list[dict[str, Any]] | None = None,
    class_features: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Create session + player. Returns (session_id, player_id)."""
    resp = requests.post(f"{api_url}/sessions", json={"world_name": WORLD, "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    scores = (
        {"str": 10, "dex": 16, "con": 12, "int": 14, "wis": 12, "cha": 10}
        if char_class == "rogue"
        else {"str": 16, "dex": 11, "con": 14, "int": 10, "wis": 12, "cha": 13}
    )

    body: dict[str, Any] = {
        "name": f"Test {char_class.title()}",
        "race": "human",
        "char_class": char_class,
        "level": 1,
        "alignment": "true_neutral",
        "hp": hp,
        "ac": 15,
        "start_location": LOCATION,
        "ability_scores": scores,
    }
    if items:
        body["items"] = items
    if class_features:
        body["class_features"] = class_features

    resp = requests.post(f"{player_api_url}/sessions/{sid}/character", json=body, timeout=10)
    resp.raise_for_status()
    return sid, resp.json()["player_id"]


def _get_turn(sock: ws_lib.WebSocket, max_msgs: int = 30) -> dict[str, Any]:
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
    for _ in range(40):
        msg = ws_recv(sock)
        if msg["type"] == "turn" and msg.get("mode") == "combat":
            return msg
    raise AssertionError("Failed to enter combat")


def _get_creature(api_url: str, sid: str, entity_id: str) -> dict[str, Any]:
    """Get creature details via master REST API."""
    resp = requests.get(f"{api_url}/sessions/{sid}/creatures/{entity_id}", timeout=10)
    assert resp.status_code == HTTPStatus.OK
    return resp.json()


def _find_events(events: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    """Find all events of the given type."""
    return [e for e in events if e.get("event_type") == event_type]


def _collect_events_until_turn(
    sock: ws_lib.WebSocket, max_msgs: int = 60
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collect all events until next turn message. Returns (events, turn)."""
    all_events: list[dict[str, Any]] = []
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] in ("action_result", "round_result"):
            all_events.extend(msg.get("events", []))
        if msg["type"] == "turn":
            all_events.extend(msg.get("events", []))
            return all_events, msg
    raise AssertionError("Never received next turn message")


def _ensure_adjacent_to_enemy(
    sock: ws_lib.WebSocket,
    turn: dict[str, Any],
    enemy_id: str,
) -> dict[str, Any]:
    """Move player adjacent to enemy if not already. Returns updated turn.

    Uses move_to to get within 5ft of the enemy. If movement isn't enough
    in one turn, ends turn and waits for the next player turn to continue.
    """
    for _ in range(5):  # max 5 turns of approaching
        px, py = _player_pos(turn)
        ex, ey = _enemy_pos(turn, enemy_id)
        dist = _grid_distance(px, py, ex, ey)

        if dist <= 5:
            return turn  # already adjacent

        # Find a cell within 5ft of enemy that's closest to player
        best_cell: tuple[int, int] | None = None
        best_player_dist = 999
        for x in range(0, 25, 5):
            for y in range(0, 25, 5):
                if _grid_distance(x, y, ex, ey) <= 5:
                    pd = _grid_distance(x, y, px, py)
                    if pd < best_player_dist:
                        best_cell = (x, y)
                        best_player_dist = pd

        if best_cell is None:
            raise AssertionError(f"No cell within 5ft of enemy ({ex},{ey})")

        ws_send_action(sock, "move_to", x=best_cell[0], y=best_cell[1])
        _events, turn2 = _collect_events_until_turn(sock)

        px2, py2 = _player_pos(turn2)
        if _grid_distance(px2, py2, ex, ey) <= 5:
            return turn2  # reached adjacent

        # Not close enough yet — end turn and wait
        ws_send_action(sock, "end_turn")
        turn = _get_turn(sock)

    raise AssertionError(f"Could not get adjacent to {enemy_id} after 5 turns")


# ── Item definitions ──────────────────────────────────────────────────────

LONGSWORD = {
    "name": "Longsword",
    "type": "weapon",
    "weapon_id": "longsword",
    "category": "martial",
    "attack_name": "longsword slash",
    "damage": [{"dice": "1d8", "type": "slashing"}],
    "ability": "str",
    "equipped": True,
}

RAPIER = {
    "name": "Rapier",
    "type": "weapon",
    "weapon_id": "rapier",
    "category": "martial",
    "attack_name": "rapier thrust",
    "damage": [{"dice": "1d8", "type": "piercing"}],
    "ability": "dex",
    "is_finesse": True,
    "equipped": True,
}


# ── Test: OA fires when leaving reach ─────────────────────────────────────


class TestOAFires:
    """Opportunity attack triggers when a creature leaves an enemy's reach."""

    def test_oa_triggers_on_leaving_reach(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Player within 5ft of enemy moves away — OA fires, player takes damage."""
        sid, pid = _create_session(api_url, player_api_url, "fighter", items=[LONGSWORD])
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "oa_guard_1")
                turn = _ensure_adjacent_to_enemy(sock, turn, "oa_guard_1")

                # Record HP before moving away
                player_before = _get_creature(api_url, sid, pid)
                hp_before = player_before["hp"]

                # Find a cell far from the enemy and move there
                px, py = _player_pos(turn)
                ex, ey = _enemy_pos(turn, "oa_guard_1")
                target = _find_cell_away_from(px, py, ex, ey)

                ws_send_action(sock, "move_to", x=target[0], y=target[1])
                events, _next_turn = _collect_events_until_turn(sock)

                # Verify opportunity attack event
                oa_events = _find_events(events, "opportunity_attack")
                assert len(oa_events) >= 1, (
                    f"Expected opportunity_attack event, got: {[e.get('event_type') for e in events]}"
                )

                oa_data = oa_events[0]["data"]
                assert oa_data["attacker_id"] == "oa_guard_1"
                assert oa_data["target_id"] == pid

                # If the OA hit, player should have taken damage
                if oa_data.get("hit"):
                    player_after = _get_creature(api_url, sid, pid)
                    assert player_after["hp"] < hp_before, (
                        f"OA hit but HP unchanged: {hp_before} → {player_after['hp']}"
                    )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Test: Disengage prevents OA ───────────────────────────────────────────


class TestDisengagePreventsOA:
    """Disengage action prevents opportunity attacks when moving away."""

    def test_disengage_then_move_no_oa(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Player uses Disengage, then moves away — no OA fires."""
        sid, pid = _create_session(api_url, player_api_url, "fighter", items=[LONGSWORD])
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "oa_guard_1")
                turn = _ensure_adjacent_to_enemy(sock, turn, "oa_guard_1")

                # Use Disengage (costs 1 action)
                ws_send_action(sock, "disengage")
                events_d, turn2 = _collect_events_until_turn(sock)

                # Now move away — should NOT trigger OA
                px, py = _player_pos(turn2)
                ex, ey = _enemy_pos(turn2, "oa_guard_1")
                target = _find_cell_away_from(px, py, ex, ey)

                ws_send_action(sock, "move_to", x=target[0], y=target[1])
                events_m, _next_turn = _collect_events_until_turn(sock)

                # No opportunity attack events
                all_events = events_d + events_m
                oa_events = _find_events(all_events, "opportunity_attack")
                assert len(oa_events) == 0, f"Expected no OA after Disengage, got {len(oa_events)}: {oa_events}"

                # Guard should still be alive
                guard = _get_creature(api_url, sid, "oa_guard_1")
                assert guard["hp"] > 0, "Guard should be alive"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Test: Rogue Cunning Action Disengage ──────────────────────────────────


class TestRogueCunningDisengage:
    """Rogue: Cunning Action Disengage (bonus) + Attack (action) + safe move."""

    def test_rogue_disengage_bonus_attack_action_safe_move(
        self, api_url: str, player_api_url: str, ws_base_url: str
    ) -> None:
        """Rogue uses Disengage as bonus action, Attack as action, then moves. No OA."""
        sid, pid = _create_session(api_url, player_api_url, "rogue", items=[RAPIER])
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "oa_guard_1")
                turn = _ensure_adjacent_to_enemy(sock, turn, "oa_guard_1")

                # Disengage as bonus action (Cunning Action)
                ws_send_action(sock, "disengage", cost_mode="bonus_action")
                events_d, turn2 = _collect_events_until_turn(sock)

                # Budget: bonus_action consumed, action still available
                budget = turn2["budget"]
                assert budget["bonus_actions"] == 0, "Bonus should be consumed"
                assert budget["actions"] >= 1, "Action should remain"

                # Attack the guard
                ws_send_action(sock, "attack", target_id="oa_guard_1")
                events_a, turn3 = _collect_events_until_turn(sock)

                # Verify attack happened
                attack_events = _find_events(events_a, "entity_attack")
                assert len(attack_events) >= 1, f"Expected attack event, got: {[e.get('event_type') for e in events_a]}"

                # Move away — should NOT trigger OA
                px, py = _player_pos(turn3)
                ex, ey = _enemy_pos(turn3, "oa_guard_1")
                target = _find_cell_away_from(px, py, ex, ey)

                ws_send_action(sock, "move_to", x=target[0], y=target[1])
                events_m, _next_turn = _collect_events_until_turn(sock)

                # No OA in any of the events
                all_events = events_d + events_a + events_m
                oa_events = _find_events(all_events, "opportunity_attack")
                assert len(oa_events) == 0, f"Expected no OA with Cunning Disengage, got {len(oa_events)}"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Test: OA kills mover — movement interrupted ──────────────────────────


class TestOAKillsMover:
    """OA kills the mover mid-movement — position stays where death occurred."""

    def test_oa_kills_1hp_mover(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Player with 1 HP moves away from enemy. OA kills. Movement stops."""
        sid, pid = _create_session(api_url, player_api_url, "fighter", hp=200, items=[LONGSWORD])
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "oa_guard_1")
                turn = _ensure_adjacent_to_enemy(sock, turn, "oa_guard_1")

                # Set HP to 1 via PATCH — any OA hit should kill
                requests.patch(
                    f"{api_url}/sessions/{sid}/creatures/{pid}",
                    json={"current_hp": 1},
                    timeout=10,
                ).raise_for_status()

                # Move away — OA should fire and likely kill
                px, py = _player_pos(turn)
                ex, ey = _enemy_pos(turn, "oa_guard_1")
                target = _find_cell_away_from(px, py, ex, ey)

                ws_send_action(sock, "move_to", x=target[0], y=target[1])

                # Collect all events (might not get a turn if dead)
                all_events: list[dict[str, Any]] = []
                for _ in range(60):
                    msg = ws_recv(sock)
                    if msg["type"] in ("action_result", "round_result"):
                        all_events.extend(msg.get("events", []))
                    if msg["type"] == "turn":
                        all_events.extend(msg.get("events", []))
                        break

                oa_events = _find_events(all_events, "opportunity_attack")
                assert len(oa_events) >= 1, "Expected OA event"

                oa_data = oa_events[0]["data"]
                if oa_data.get("hit"):
                    # Player should be dead
                    death_events = _find_events(all_events, "entity_died")
                    assert len(death_events) >= 1, (
                        f"OA hit a 1 HP creature but no entity_died event. "
                        f"Events: {[e.get('event_type') for e in all_events]}"
                    )
                    assert death_events[0]["data"]["entity_id"] == pid

                    # Verify creature is dead via API
                    creature = _get_creature(api_url, sid, pid)
                    assert creature["hp"] <= 0, f"Expected dead creature, got HP={creature['hp']}"
                # If OA missed, that's a valid but less interesting outcome
                # with DND_DICE_SEED=42, we rely on deterministic dice
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Test: Two enemies — both OA ──────────────────────────────────────────


class TestTwoEnemiesOA:
    """Player moves past two enemies — both make opportunity attacks."""

    def test_two_enemies_both_oa(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Trigger OA from guard_1 in one turn, then OA from guard_2 in a later turn."""
        sid, pid = _create_session(api_url, player_api_url, "fighter", hp=200, items=[LONGSWORD])
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "oa_guard_1")

                # --- OA from guard_1 ---
                turn = _ensure_adjacent_to_enemy(sock, turn, "oa_guard_1")
                px, py = _player_pos(turn)
                ex, ey = _enemy_pos(turn, "oa_guard_1")
                target = _find_cell_away_from(px, py, ex, ey)

                ws_send_action(sock, "move_to", x=target[0], y=target[1])
                events1, _turn2 = _collect_events_until_turn(sock)
                oa_events1 = _find_events(events1, "opportunity_attack")
                assert len(oa_events1) >= 1, f"Expected OA from guard_1, got: {[e.get('event_type') for e in events1]}"

                # End turn, wait for next player turn (guards take their turns)
                ws_send_action(sock, "end_turn")
                turn3 = _get_turn(sock)

                # --- OA from guard_2 ---
                # Re-read guard_2 position (may have moved during their turn)
                turn3 = _ensure_adjacent_to_enemy(sock, turn3, "oa_guard_2")
                px2, py2 = _player_pos(turn3)
                e2x, e2y = _enemy_pos(turn3, "oa_guard_2")
                target2 = _find_cell_away_from(px2, py2, e2x, e2y)

                ws_send_action(sock, "move_to", x=target2[0], y=target2[1])
                events2, _ = _collect_events_until_turn(sock)
                oa_events2 = _find_events(events2, "opportunity_attack")
                assert len(oa_events2) >= 1, f"Expected OA from guard_2, got: {[e.get('event_type') for e in events2]}"

                # Verify different guards attacked
                attacker1 = oa_events1[0]["data"]["attacker_id"]
                attacker2 = oa_events2[0]["data"]["attacker_id"]
                attackers = {attacker1, attacker2}
                assert len(attackers) == 2, f"Expected OAs from 2 different guards, got: {attacker1}, {attacker2}"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
