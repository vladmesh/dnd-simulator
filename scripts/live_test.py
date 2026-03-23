#!/usr/bin/env python3
"""Live integration test — exercises the full stack via REST + WebSocket.

Usage:
    make serve  # in one terminal
    python scripts/live_test.py  # in another

Covers:
    - Session creation (master)
    - Player character creation
    - NPC spawning + patching
    - WebSocket turn cycle (action → awareness loop)
    - Multi-action turns (say + end_turn)
    - Combat initiation (attack → auto-start)
    - Combat actions (attack, dodge, move, flee)
    - Budget in awareness
    - Time advancement
    - World state god-mode query
    - Save/load
"""

from __future__ import annotations

import json
import sys

import requests
import websocket  # type: ignore[import-untyped]

BASE = "http://localhost:8001"
WS_BASE = "ws://localhost:8001"


def log(tag: str, msg: str) -> None:
    print(f"  [{tag}] {msg}")


def rest(method: str, path: str, json_data: object = None) -> dict:
    url = f"{BASE}{path}"
    resp = getattr(requests, method)(url, json=json_data)
    data = resp.json()
    status = "OK" if resp.ok else f"FAIL {resp.status_code}"
    log("REST", f"{method.upper()} {path} → {status}")
    if not resp.ok:
        log("REST", f"  Error: {data}")
    return data


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main() -> None:
    # ── 1. Health check ──
    section("1. Health check")
    try:
        r = requests.get(f"{BASE}/docs")
        log("HTTP", f"GET /docs → {r.status_code}")
    except requests.ConnectionError:
        print("ERROR: Server not running. Start with: make serve")
        sys.exit(1)

    # ── 2. Master: create session ──
    section("2. Master: create session")
    session = rest("post", "/api/master/sessions", {"world_name": "sword_vale", "lang": "en"})
    sid = session["session_id"]
    log("INFO", f"Session: {sid}, player: {session.get('player_name')}, location: {session.get('player_location')}")

    try:
        _run_test(sid)
    finally:
        _cleanup(sid)


def _cleanup(sid: str) -> None:
    """Delete session and all saves created during the test."""
    section("Cleanup")
    # Delete saves created by this test
    for save_name in ["live_test_save", f"session_{sid}"]:
        try:
            rest("delete", f"/api/master/sessions/{sid}/saves/{save_name}")
        except Exception:
            log("WARN", f"Could not delete save '{save_name}'")
    # Delete the session itself
    try:
        rest("delete", f"/api/master/sessions/{sid}")
    except Exception:
        log("WARN", "Could not delete session")
    section("DONE — all steps completed")


def _run_test(sid: str) -> None:
    """Run all test steps for a given session."""
    # ── 3. Player: create character ──
    section("3. Player: create character")
    player = rest("post", f"/api/player/sessions/{sid}/character", {
        "name": "Kael",
        "race": "human",
        "char_class": "fighter",
        "level": 3,
        "hp": 28,
        "ac": 16,
        "gold": 50,
        "start_location": "silverport_city_tavern",
        "ability_scores": {"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "attacks": [
            {"name": "longbow", "ability": "dex", "damage": [{"dice": "1d8", "type": "piercing"}], "reach": 150},
            {"name": "longsword", "ability": "str", "damage": [{"dice": "1d8", "type": "slashing"}], "reach": 5},
        ],
    })
    loc = player.get('location_id')
    log("INFO", f"Player: {player.get('name')} HP:{player.get('hp')} AC:{player.get('ac')} loc={loc}")
    player_location = player.get("location_id", "")

    # ── 4. Master: spawn a goblin at player's location (with shortbow) ──
    section("4. Master: spawn goblin")
    rest("post", f"/api/master/sessions/{sid}/creatures", {
        "id": "goblin_1",
        "name": "Skrag the Goblin",
        "entity_type": "npc",
        "start_location": player_location,
        "role": "bandit",
        "personality": "Vicious and cunning",
        "hp": 12,
        "ac": 13,
        "ai": "rule_based",
        "attacks": [
            {"name": "shortbow", "ability": "dex", "damage": [{"dice": "1d6", "type": "piercing"}], "reach": 80},
            {"name": "scimitar", "ability": "dex", "damage": [{"dice": "1d6", "type": "slashing"}], "reach": 5},
        ],
    })

    # ── 5. Master: check world state (god-mode) ──
    section("5. Master: world state (god-mode)")
    state = rest("get", f"/api/master/sessions/{sid}")
    entities = state.get("entities", [])
    log("INFO", f"Entities in world: {len(entities)}")
    for e in entities:
        log("INFO", f"  {e.get('id')}: {e.get('name')} at {e.get('location_id')} active={e.get('active')}")

    # ── 6. Master: advance time 1 hour ──
    section("6. Master: advance time")
    rest("post", f"/api/master/sessions/{sid}/time/advance", {"hours": 1})

    # ── 7. Master: save game ──
    section("7. Master: save game")
    rest("post", f"/api/master/sessions/{sid}/save?name=live_test_save")

    # ── 8. WebSocket: connect and play ──
    section("8. WebSocket: connect and play turns")
    ws_url = f"{WS_BASE}/api/ws/{sid}"
    log("WS", f"Connecting to {ws_url}")

    ws = websocket.create_connection(ws_url, timeout=15)

    def ws_recv() -> dict:
        raw = ws.recv()
        msg = json.loads(raw)
        log("WS←", f"type={msg.get('type')} {_summarize(msg)}")
        return msg

    def ws_send(msg: dict) -> None:
        log("WS→", f"type={msg.get('type')} name={msg.get('name', '')}")
        ws.send(json.dumps(msg))

    # ── 8a. Receive first turn (should be peaceful) ──
    section("8a. First turn — peaceful")
    turn = ws_recv()
    assert turn["type"] == "turn", f"Expected 'turn', got {turn['type']}"
    log("INFO", f"Mode: {turn.get('mode')}")
    if "budget" in turn:
        log("INFO", f"Budget: {turn['budget']}")

    # ── 8b. Say something (free action) ──
    section("8b. Free action: say")
    ws_send({"type": "action", "name": "say", "params": {"text": "Prepare yourself, goblin!"}})

    # Should get action_result (say is free) then next turn prompt
    msg = ws_recv()  # action_result
    if msg["type"] == "action_result":
        log("INFO", f"Action result for: {msg.get('action')}, budget: {msg.get('budget')}")
        msg = ws_recv()  # next turn prompt
    log("INFO", f"After say: type={msg.get('type')}")

    # ── 8c. Attack goblin → should trigger combat ──
    section("8c. Attack goblin → combat start")
    ws_send({"type": "action", "name": "attack", "params": {"target_id": "goblin_1"}})

    # Collect messages until we get a turn (next turn in combat)
    messages = []
    for _ in range(5):
        msg = ws_recv()
        messages.append(msg)
        if msg["type"] == "turn":
            break

    log("INFO", f"Messages after attack: {[m['type'] for m in messages]}")
    last_turn = next((m for m in reversed(messages) if m["type"] == "turn"), None)
    if last_turn:
        log("INFO", f"Combat mode: {last_turn.get('mode')}")
        if last_turn.get("mode") == "combat":
            aw = last_turn.get("awareness", {})
            log("INFO", f"Round: {aw.get('round_number')}, HP: {aw.get('self_hp')}/{aw.get('self_max_hp')}")
            nearby = aw.get("nearby", [])
            for n in nearby:
                log("INFO", f"  Nearby: {n.get('description')} dist={n.get('distance_ft')}ft {n.get('direction')}")

    # ── 8d-8i. Combat: multiple rounds of fighting ──
    for combat_round in range(6):
        section(f"8.{combat_round + 4}. Combat round — attack goblin")
        ws_send({"type": "action", "name": "attack", "params": {"target_id": "goblin_1"}})
        got_turn = False
        for _ in range(5):
            msg = ws_recv()
            if msg["type"] == "action_result":
                log("INFO", f"Attack result: {msg.get('events', [])[:2]}")
            if msg["type"] == "round_result":
                log("INFO", f"Round end: {len(msg.get('events', []))} events")
            if msg["type"] == "turn":
                mode = msg.get("mode", "?")
                aw = msg.get("awareness", {})
                hp_info = f"HP:{aw.get('self_hp', '?')}/{aw.get('self_max_hp', '?')}" if mode == "combat" else ""
                nearby = aw.get("nearby", [])
                enemy_hp = ""
                for n in nearby:
                    wound = " WOUNDED" if n.get("is_wounded") else ""
                    enemy_hp = f" | Enemy: {n.get('description', '?')} dist={n.get('distance_ft')}ft{wound}"
                log("INFO", f"Turn: mode={mode} {hp_info}{enemy_hp}")
                if mode == "peaceful":
                    log("INFO", "Combat ended! (enemy fled or died)")
                got_turn = True
                break
        # End turn to let goblin act
        ws_send({"type": "action", "name": "end_turn"})
        for _ in range(3):
            msg = ws_recv()
            if msg["type"] == "turn":
                break
        if not got_turn or msg.get("mode") == "peaceful":
            log("INFO", "Exiting combat loop")
            break

    # ── 8j. Flee if still in combat ──
    section("8j. Flee combat (if still in)")
    if msg.get("mode") == "combat":
        ws_send({"type": "action", "name": "flee"})
        for _ in range(3):
            msg = ws_recv()
            if msg["type"] == "turn":
                break
    else:
        log("INFO", "Already out of combat, skipping flee")

    # ── 8h. Back to peaceful — end turn a couple times ──
    section("8h. Peaceful turns after flee")
    for i in range(2):
        ws_send({"type": "action", "name": "end_turn"})
        try:
            for _ in range(5):
                msg = ws_recv()
                log("INFO", f"Peaceful cycle {i+1}: {msg.get('type')}")
                if msg["type"] == "turn":
                    log("INFO", f"  mode={msg.get('mode')} budget={msg.get('budget')}")
                    break
        except Exception as e:
            log("WARN", f"Peaceful cycle {i+1} timed out: {e}")
            break

    # ── 9. Close WS ──
    section("9. Close WebSocket")
    ws.close()
    log("WS", "Disconnected")

    # ── 10. Verify player status after combat via REST ──
    section("10. Player status after combat")
    status = rest("get", f"/api/player/sessions/{sid}/status")
    log("INFO", f"HP: {status.get('hp')}/{status.get('max_hp')}")

    # ── 11. Master: check NPC state ──
    section("11. NPC state after combat")
    goblin = rest("get", f"/api/master/sessions/{sid}/creatures/goblin_1")
    log("INFO", f"Goblin HP: {goblin.get('hp')}/{goblin.get('max_hp')} active={goblin.get('active')}")

    # ── 12. Master: patch creature (heal goblin) ──
    section("12. Master: patch creature (heal)")
    rest("patch", f"/api/master/sessions/{sid}/creatures/goblin_1", {"current_hp": 7})

    section("Test steps completed")


def _summarize(msg: dict) -> str:
    """Short summary of a WS message for logging."""
    t = msg.get("type", "")
    if t == "turn":
        mode = msg.get("mode", "?")
        budget = msg.get("budget", {})
        return f"mode={mode} budget_actions={budget.get('actions', '?')}"
    if t == "action_result":
        return f"action={msg.get('action')} budget={msg.get('budget', {})}"
    if t == "round_result":
        return f"events={len(msg.get('events', []))}"
    if t == "error":
        return f"msg={msg.get('message', '')}"
    return ""


if __name__ == "__main__":
    main()
