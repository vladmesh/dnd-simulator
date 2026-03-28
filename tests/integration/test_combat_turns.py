"""Integration tests: Full Fighter & Rogue combat turns through the live API.

Tests run against a live backend in docker compose with:
- DND_DICE_SEED=42 (deterministic rolls)
- combat_test world: 3x3 battle map, faction-aware NPCs, all rule-based

Each test creates its own session to avoid state pollution.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action

WORLD = "combat_test"
LOCATION = "combat_floor"


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_session(
    api_url: str,
    player_api_url: str,
    char_class: str,
    *,
    hp: int = 30,
    ac: int = 15,
    ability_scores: dict[str, int] | None = None,
    items: list[dict[str, Any]] | None = None,
    class_features: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Create session + player character. Returns (session_id, player_id).

    Items with ``equipped: true`` are auto-equipped at creation time.
    """
    resp = requests.post(f"{api_url}/sessions", json={"world_name": WORLD, "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    scores = ability_scores or (
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
        "ac": ac,
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


def _find_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    """Find first event of the given type."""
    for e in events:
        if e.get("event_type") == event_type:
            return e
    return None


def _collect_events_until_turn(
    sock: ws_lib.WebSocket,
    max_msgs: int = 40,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collect all events from action_result and round_result messages until next turn.

    Returns (all_events, turn_msg).
    """
    all_events: list[dict[str, Any]] = []
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] in ("action_result", "round_result"):
            all_events.extend(msg.get("events", []))
        if msg["type"] == "turn":
            all_events.extend(msg.get("events", []))
            return all_events, msg
    raise AssertionError("Never received next turn message")


# ── Fighter items ────────────────────────────────────────────────────────

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

CHAIN_MAIL = {
    "name": "Chain Mail",
    "type": "armor",
    "armor_id": "chain_mail",
    "category": "heavy",
    "base_ac": 16,
    "strength_req": 13,
    "max_dex_bonus": 0,
    "equipped": True,
}

SHIELD = {
    "name": "Shield",
    "type": "shield",
    "shield_id": "shield",
    "ac_bonus": 2,
    "equipped": True,
}

# ── Rogue items ──────────────────────────────────────────────────────────

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

STUDDED_LEATHER = {
    "name": "Studded Leather",
    "type": "armor",
    "armor_id": "studded_leather",
    "category": "light",
    "base_ac": 12,
    "equipped": True,
}


# ── Test: Fighter Full Turn ──────────────────────────────────────────────


class TestFighterFullTurn:
    """Fighter with Defense style, chain mail, shield, longsword through full combat turn."""

    def test_fighter_ac_composition_and_attack(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Fighter: chain_mail(16) + shield(+2) + defense(+1) = AC 19. Attack hits and deals damage."""
        sid, pid = _create_session(
            api_url,
            player_api_url,
            "fighter",
            hp=40,
            ac=16,
            items=[LONGSWORD, CHAIN_MAIL, SHIELD],
            class_features={"fighting_style": "defense"},
        )
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)

                # Verify AC: chain_mail(16) + shield(+2) + defense(+1) = 19
                assert turn["player"]["ac"] == 19, (
                    f"Expected AC 19 (chain_mail 16 + shield 2 + defense 1), got {turn['player']['ac']}"
                )

                # Enter combat
                turn = _ensure_combat(sock, turn, "target_dummy")

                # Verify equipped weapon in combat awareness
                equipped = turn["player"]["equipped"]
                weapon = next((e for e in equipped if e["slot"] == "weapon"), None)
                assert weapon is not None, "Longsword should be equipped"

                # Attack the dummy (AC 8 — should hit with seed=42)
                dummy_before = _get_creature(api_url, sid, "target_dummy")
                hp_before = dummy_before["hp"]

                ws_send_action(sock, "attack", target_id="target_dummy")
                events, _next_turn = _collect_events_until_turn(sock)

                # Find attack event
                attack_event = _find_event(events, "entity_attack")
                assert attack_event is not None, (
                    f"Expected entity_attack event, got: {[e.get('event_type') for e in events]}"
                )

                attack_data = attack_event["data"]
                assert attack_data["attacker_id"] == pid
                assert attack_data["target_id"] == "target_dummy"

                if attack_data["hit"]:
                    assert attack_data["damage"] > 0
                    dummy_after = _get_creature(api_url, sid, "target_dummy")
                    assert dummy_after["hp"] == hp_before - attack_data["damage"]
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_fighter_second_wind_heals_and_exhausts(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Fighter uses Second Wind (bonus action): heals 1d10+level, resource consumed. Second use fails."""
        sid, pid = _create_session(api_url, player_api_url, "fighter", hp=40, ac=16, items=[LONGSWORD])
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "target_dummy")

                # Damage the fighter first via PATCH so Second Wind has something to heal
                requests.patch(
                    f"{api_url}/sessions/{sid}/creatures/{pid}",
                    json={"current_hp": 10},
                    timeout=10,
                ).raise_for_status()

                # Verify fighter has second_wind resource
                creature = _get_creature(api_url, sid, pid)
                pools = {p["id"]: p for p in creature.get("resource_pools", [])}
                assert "second_wind" in pools, f"Fighter should have second_wind resource, got: {list(pools)}"
                assert pools["second_wind"]["current_uses"] == 1

                # Use Second Wind
                ws_send_action(sock, "second_wind")
                events, turn2 = _collect_events_until_turn(sock)

                # Check healing event
                sw_event = _find_event(events, "entity_second_wind")
                assert sw_event is not None, (
                    f"Expected entity_second_wind event, got: {[e.get('event_type') for e in events]}"
                )
                healed = sw_event["data"]["healed"]
                assert healed > 0, "Second Wind should heal at least 1 HP"

                # Player HP should have increased
                assert turn2["player"]["hp"] > 10, f"HP should be > 10 after healing, got {turn2['player']['hp']}"

                # Resource should be exhausted
                creature2 = _get_creature(api_url, sid, pid)
                pools2 = {p["id"]: p for p in creature2.get("resource_pools", [])}
                assert pools2["second_wind"]["current_uses"] == 0, "Second wind should be exhausted"

                # Second attempt should fail — end turn first, then try again
                ws_send_action(sock, "end_turn")
                turn3 = _get_turn(sock)
                # Wait for player's next turn
                while turn3.get("budget", {}).get("actions", 0) == 0:
                    turn3 = _get_turn(sock)

                # Second wind should not be in available_actions (resource exhausted)
                actions = {a["name"] for a in turn3["awareness"]["available_actions"]}
                assert "second_wind" not in actions, "Second Wind should not be available after resource exhaustion"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Test: Rogue Full Turn ────────────────────────────────────────────────


class TestRogueFullTurn:
    """Rogue with rapier, studded leather: Cunning Action, sneak attack, budget enforcement."""

    def test_rogue_cunning_dash_then_attack_with_sneak_attack(
        self, api_url: str, player_api_url: str, ws_base_url: str
    ) -> None:
        """Rogue uses Cunning Action DASH as bonus_action, then attacks.

        On 3x3 map with ally_fighter_npc adjacent to target, sneak attack triggers.
        """
        sid, pid = _create_session(api_url, player_api_url, "rogue", hp=20, ac=12, items=[RAPIER, STUDDED_LEATHER])
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "target_dummy")

                # Verify rogue has cost_options for dash
                actions = {a["name"]: a for a in turn["awareness"]["available_actions"]}
                assert "dash" in actions
                dash = actions["dash"]
                assert "cost_options" in dash, "Rogue should have cost_options on dash"

                # Use Cunning Action DASH as bonus action
                ws_send_action(sock, "dash", cost_mode="bonus_action")
                turn2 = _get_turn(sock)

                # Bonus action consumed, action still available
                budget = turn2["budget"]
                assert budget["actions"] >= 1, "Action should remain after bonus-action dash"
                assert budget["bonus_actions"] == 0, "Bonus action should be consumed"

                # Now attack the dummy — should have sneak attack (ally adjacent on tiny map)
                ws_send_action(sock, "attack", target_id="target_dummy")
                events, _ = _collect_events_until_turn(sock)

                attack_event = _find_event(events, "entity_attack")
                assert attack_event is not None, "Expected entity_attack event"

                attack_data = attack_event["data"]
                if attack_data["hit"]:
                    # Check for sneak attack damage component
                    damage_sources = [d["source"] for d in attack_data.get("damage_components", [])]
                    assert "sneak_attack" in damage_sources, (
                        f"Sneak attack should trigger with ally adjacent, got sources: {damage_sources}"
                    )
                    assert attack_data["damage"] > 0
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_rogue_attack_budget_enforcement(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Rogue attacks once (action consumed), second attack rejected (no budget)."""
        sid, pid = _create_session(api_url, player_api_url, "rogue", hp=20, ac=12, items=[RAPIER])
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "target_dummy")

                # First attack — should succeed
                ws_send_action(sock, "attack", target_id="target_dummy")
                turn2 = _get_turn(sock)

                # Action should be consumed
                budget = turn2["budget"]
                assert budget["actions"] == 0, "Action should be consumed after attack"

                # Attack should NOT be in available actions anymore
                action_names = {a["name"] for a in turn2["awareness"]["available_actions"]}
                assert "attack" not in action_names, (
                    f"Attack should not be available with 0 actions, but available: {action_names}"
                )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Test: Mixed Combat — Faction-Aware Sneak Attack ──────────────────────


class TestMixedCombatFactionSneakAttack:
    """Fighter + Rogue vs enemy: faction-aware sneak attack with ally adjacency."""

    def test_rogue_sneak_attack_with_fighter_ally_adjacent(
        self, api_url: str, player_api_url: str, ws_base_url: str
    ) -> None:
        """Rogue player attacks dummy with allied Fighter NPC adjacent — sneak attack triggers.

        The combat_test world has ally_fighter_npc (hero_faction) and target_dummy (enemy_faction).
        Player gets hero_faction from manifest default_player_faction.
        On a 3x3 map, all entities are adjacent.
        """
        sid, pid = _create_session(api_url, player_api_url, "rogue", hp=20, ac=12, items=[RAPIER, STUDDED_LEATHER])
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "target_dummy")

                # Attack the dummy — allied NPC should be adjacent on 3x3 map
                ws_send_action(sock, "attack", target_id="target_dummy")
                events, _ = _collect_events_until_turn(sock)

                attack_event = _find_event(events, "entity_attack")
                assert attack_event is not None, "Expected entity_attack event"

                attack_data = attack_event["data"]
                if attack_data["hit"]:
                    # Sneak attack should trigger: ally_fighter_npc is hero_faction,
                    # adjacent to target_dummy (enemy_faction), and rogue has finesse weapon
                    damage_sources = [d["source"] for d in attack_data.get("damage_components", [])]
                    assert "sneak_attack" in damage_sources, (
                        f"Sneak attack should trigger with allied fighter adjacent. "
                        f"Damage sources: {damage_sources}, full data: {attack_data}"
                    )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_fighter_player_no_sneak_attack(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Fighter player attacks dummy — no sneak attack (wrong class)."""
        sid, pid = _create_session(api_url, player_api_url, "fighter", hp=40, ac=16, items=[LONGSWORD])
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "target_dummy")

                ws_send_action(sock, "attack", target_id="target_dummy")
                events, _ = _collect_events_until_turn(sock)

                attack_event = _find_event(events, "entity_attack")
                assert attack_event is not None, "Expected entity_attack event"

                attack_data = attack_event["data"]
                if attack_data["hit"]:
                    damage_sources = [d["source"] for d in attack_data.get("damage_components", [])]
                    assert "sneak_attack" not in damage_sources, (
                        f"Fighter should NOT get sneak attack, but got sources: {damage_sources}"
                    )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
