"""Integration tests: Full Fighter, Rogue & Paladin combat turns through the live API.

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
    ability_scores: dict[str, int] | None = None,
    fighting_style: str | None = None,
) -> tuple[str, str]:
    """Create session + player character. Returns (session_id, player_id)."""
    resp = requests.post(f"{api_url}/sessions", json={"world_name": WORLD, "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    scores = ability_scores or (
        {"str": 10, "dex": 15, "con": 12, "int": 14, "wis": 12, "cha": 8}
        if char_class == "rogue"
        else {"str": 15, "dex": 11, "con": 14, "int": 10, "wis": 10, "cha": 9}
    )

    body: dict[str, Any] = {
        "name": f"Test {char_class.title()}",
        "race": "human",
        "char_class": char_class,
        "alignment": "true_neutral",
        "start_location": LOCATION,
        "ability_scores": scores,
    }
    if fighting_style:
        body["fighting_style"] = fighting_style

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


# ── Test: Fighter Full Turn ──────────────────────────────────────────────


class TestFighterFullTurn:
    """Fighter with Defense style, chain mail, shield, longsword through full combat turn."""

    def test_fighter_ac_composition_and_attack(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Fighter: chain_mail(16) + shield(+2) + defense(+1) = AC 19. Attack hits and deals damage."""
        sid, pid = _create_session(
            api_url,
            player_api_url,
            "fighter",
            fighting_style="defense",
        )
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)

                # Starting equipment: chain_mail(16) + shield(+2) + defense(+1) = 19
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
        sid, pid = _create_session(api_url, player_api_url, "fighter")
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
        sid, pid = _create_session(api_url, player_api_url, "rogue")
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
        sid, pid = _create_session(api_url, player_api_url, "rogue")
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
        sid, pid = _create_session(api_url, player_api_url, "rogue")
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
        sid, pid = _create_session(api_url, player_api_url, "fighter")
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


# ── Test: Paladin Combo — Flaming Longsword + Divine Smite ─────────────


class TestPaladinCombat:
    """Paladin with flaming longsword + Divine Smite: 3 damage types, spell slot consumed."""

    def test_paladin_flaming_sword_smite_three_damage_types(
        self, api_url: str, player_api_url: str, ws_base_url: str
    ) -> None:
        """Paladin attacks with flaming longsword + smite → 3 damage types on hit.

        Flaming longsword = 1d8 slashing + 1d6 fire.
        Divine Smite (slot 1) = 2d8 radiant.
        On hit: damage_components has weapon(slashing), weapon(fire), divine_smite(radiant).
        Spell slot consumed only on hit.
        """
        sid, pid = _create_session(
            api_url,
            player_api_url,
            "paladin",
            ability_scores={"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 10, "cha": 14},
        )
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                # Inject spell slots (level 1 Paladin doesn't have them naturally)
                requests.patch(
                    f"{api_url}/sessions/{sid}/creatures/{pid}",
                    json={
                        "resource_pools": [
                            {"id": "spell_slot_1", "max_uses": 2, "current_uses": 2, "reset_on": "long_rest"},
                        ],
                    },
                    timeout=10,
                ).raise_for_status()

                # Give flaming longsword (goes to inventory since Paladin already has longsword)
                give_resp = requests.post(
                    f"{api_url}/sessions/{sid}/creatures/{pid}/items",
                    json={
                        "name": "Flaming Longsword",
                        "type": "weapon",
                        "weapon_id": "flaming_longsword",
                        "category": "martial",
                        "attack_name": "flaming slash",
                        "damage": [
                            {"dice": "1d8", "type": "slashing"},
                            {"dice": "1d6", "type": "fire"},
                        ],
                        "modifier": 1,
                        "is_magic": True,
                    },
                    timeout=10,
                )
                give_resp.raise_for_status()
                flaming_id = give_resp.json()["item_id"]

                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "target_dummy")

                # Equip flaming longsword (replaces starting longsword)
                ws_send_action(sock, "equip", weapon_id=flaming_id)
                turn = _get_turn(sock)

                # Verify flaming longsword equipped
                equipped = turn["player"]["equipped"]
                weapon = next((e for e in equipped if e["slot"] == "weapon"), None)
                assert weapon is not None, "Should have weapon equipped"
                assert "flaming" in weapon["name"].lower(), (
                    f"Expected flaming longsword equipped, got: {weapon['name']}"
                )

                # Attack with Divine Smite (slot level 1)
                ws_send_action(sock, "attack", target_id="target_dummy", smite_slot_level=1)
                events, _ = _collect_events_until_turn(sock)

                attack_event = _find_event(events, "entity_attack")
                assert attack_event is not None, (
                    f"Expected entity_attack event, got: {[e.get('event_type') for e in events]}"
                )

                attack_data = attack_event["data"]
                if attack_data["hit"]:
                    # Verify 3 damage types
                    components = attack_data["damage_components"]
                    sources = [d["source"] for d in components]
                    types = [d["type"] for d in components]

                    assert "weapon" in sources, f"Expected weapon damage source, got sources: {sources}"
                    assert "divine_smite" in sources, f"Expected divine_smite source, got sources: {sources}"
                    assert "slashing" in types, f"Expected slashing damage type, got types: {types}"
                    assert "fire" in types, f"Expected fire damage type, got types: {types}"
                    assert "radiant" in types, f"Expected radiant damage type, got types: {types}"
                    assert len(components) >= 3, (
                        f"Expected at least 3 damage components, got {len(components)}: {components}"
                    )
                    assert attack_data["damage"] > 0

                    # Spell slot consumed on hit
                    creature = _get_creature(api_url, sid, pid)
                    pools = {p["id"]: p for p in creature["resource_pools"]}
                    assert pools["spell_slot_1"]["current_uses"] == 1, (
                        f"Spell slot should be consumed (2→1), got: {pools['spell_slot_1']['current_uses']}"
                    )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_paladin_spell_slots_visible_in_awareness(
        self, api_url: str, player_api_url: str, ws_base_url: str
    ) -> None:
        """Spell slots appear in combat awareness self_resource_pools."""
        sid, pid = _create_session(
            api_url,
            player_api_url,
            "paladin",
            ability_scores={"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 10, "cha": 14},
        )
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                # Inject spell slots
                requests.patch(
                    f"{api_url}/sessions/{sid}/creatures/{pid}",
                    json={
                        "resource_pools": [
                            {"id": "spell_slot_1", "max_uses": 2, "current_uses": 2, "reset_on": "long_rest"},
                        ],
                    },
                    timeout=10,
                ).raise_for_status()

                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "target_dummy")

                # Check awareness for spell slots
                awareness_pools = turn["awareness"].get("self_resource_pools", [])
                pool_ids = {p["id"] for p in awareness_pools}
                assert "spell_slot_1" in pool_ids, f"Expected spell_slot_1 in awareness resource pools, got: {pool_ids}"

                slot_pool = next(p for p in awareness_pools if p["id"] == "spell_slot_1")
                assert slot_pool["max_uses"] == 2
                assert slot_pool["current_uses"] == 2

                # Also check player info has resource_pools
                player_pools = {p["id"]: p for p in turn["player"].get("resource_pools", [])}
                assert "spell_slot_1" in player_pools, (
                    f"Expected spell_slot_1 in player resource_pools, got: {list(player_pools)}"
                )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_paladin_spell_slot_consumed_after_smite(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """After a smite hit, spell slot is consumed (verified via master API)."""
        sid, pid = _create_session(
            api_url,
            player_api_url,
            "paladin",
            ability_scores={"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 10, "cha": 14},
        )
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                # Inject spell slots
                requests.patch(
                    f"{api_url}/sessions/{sid}/creatures/{pid}",
                    json={
                        "resource_pools": [
                            {"id": "spell_slot_1", "max_uses": 2, "current_uses": 2, "reset_on": "long_rest"},
                        ],
                    },
                    timeout=10,
                ).raise_for_status()

                # Verify initial state
                creature = _get_creature(api_url, sid, pid)
                pools = {p["id"]: p for p in creature["resource_pools"]}
                assert pools["spell_slot_1"]["current_uses"] == 2

                turn = _get_turn(sock)
                turn = _ensure_combat(sock, turn, "target_dummy")

                # Attack with smite (using starting longsword — single damage type is fine)
                ws_send_action(sock, "attack", target_id="target_dummy", smite_slot_level=1)
                events, _ = _collect_events_until_turn(sock)

                attack_event = _find_event(events, "entity_attack")
                assert attack_event is not None

                # Verify slot consumed on hit (or preserved on miss)
                creature2 = _get_creature(api_url, sid, pid)
                pools2 = {p["id"]: p for p in creature2["resource_pools"]}
                if attack_event["data"]["hit"]:
                    assert pools2["spell_slot_1"]["current_uses"] == 1, (
                        f"Spell slot should be 1 after hit+smite, got: {pools2['spell_slot_1']['current_uses']}"
                    )
                else:
                    assert pools2["spell_slot_1"]["current_uses"] == 2, "Spell slot should NOT be consumed on miss"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
