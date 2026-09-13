#!/usr/bin/env python3
"""Run the manual real-model inner-self scenario against ``make serve``.

The script never starts a server. Export OPENROUTER_API_KEY and LLM_MODEL in
the server environment, then run ``make live-inner-self`` from another shell.
Set DND_LIVE_LOG to that server's fresh JSON log file for digest/retry counts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Never

import requests
import websocket  # type: ignore[import-untyped]

from dnd_simulator.live_inner_self_report import classify_report

BASE = "http://localhost:8001"
WS_BASE = "ws://localhost:8001"


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def skipped(message: str) -> Never:
    print(f"SKIPPED / NOT RUNNABLE: {message}")
    raise SystemExit(2)


def rest(method: str, path: str, body: object | None = None) -> dict[str, object]:
    response = requests.request(method, f"{BASE}{path}", json=body, timeout=20)
    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}
    if not response.ok:
        raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {data}")
    if not isinstance(data, dict):
        raise RuntimeError(f"{method} {path}: expected JSON object")
    return data


def snapshot(sid: str, label: str) -> dict[str, object]:
    state = rest("get", f"/api/master/sessions/{sid}/creatures/live_npc/inner-self")
    section(label)
    print(json.dumps(state, ensure_ascii=False, indent=2, default=str))
    return state


def drive_player(sid: str) -> None:
    """Attack the NPC, then leave combat; tolerate model-specific combat length."""
    ws = websocket.create_connection(f"{WS_BASE}/api/ws/{sid}", timeout=45)
    try:
        ws.recv()  # initial player turn
        for action in (
            {"type": "action", "name": "attack", "params": {"target_id": "live_npc"}},
            {"type": "action", "name": "flee", "params": {}},
            {"type": "action", "name": "wait", "params": {"hours": 1}},
        ):
            ws.send(json.dumps(action))
            for _ in range(12):
                message = json.loads(ws.recv())
                if message.get("type") == "turn":
                    break
    finally:
        ws.close()


def log_metrics() -> dict[str, object]:
    log_path = os.getenv("DND_LIVE_LOG")
    if not log_path:
        return {"available": False, "reason": "Set DND_LIVE_LOG to the fresh server JSON log."}
    try:
        paths = [Path(log_path)]
        if paths[0].is_dir():
            paths = list(paths[0].rglob("*.jsonl"))
        records = [json.loads(line) for path in paths for line in path.read_text().splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        return {"available": False, "reason": f"Cannot read DND_LIVE_LOG: {error}"}
    events = [record.get("event") for record in records if isinstance(record, dict)]
    accepted = [
        record for record in records if isinstance(record, dict) and record.get("event") == "llm_tool_call_accepted"
    ]
    return {
        "available": True,
        "accepted_digests": events.count("inner_self_llm_digest_accepted"),
        "fallback_digests": events.count("inner_self_llm_digest_rejected"),
        "rejected_tool_calls": events.count("llm_tool_call_rejected"),
        "accepted_tool_calls": len(accepted),
        "retries_before_valid": [record.get("retries") for record in accepted],
        "digest_response_formats": [
            record.get("response_format")
            for record in records
            if isinstance(record, dict) and record.get("event") == "inner_self_llm_digest_accepted"
        ],
    }


def report(before: dict[str, object], after_combat: dict[str, object], after_anchor: dict[str, object]) -> None:
    metrics = log_metrics()
    section("Real-model assumptions")
    print(f"LLM_MODEL={os.environ['LLM_MODEL']}")
    print(json.dumps(metrics, ensure_ascii=False, indent=2, default=str))
    for check in classify_report(before, after_combat, after_anchor, metrics):
        print(f"{'PASS' if check['passed'] else 'WARN'}: {check['name']}")


def main() -> None:
    if not os.getenv("OPENROUTER_API_KEY") or not os.getenv("LLM_MODEL"):
        skipped("OPENROUTER_API_KEY and LLM_MODEL must be exported for this real-model scenario.")
    try:
        requests.get(f"{BASE}/health", timeout=3).raise_for_status()
    except requests.RequestException:
        skipped("Server is not running at http://localhost:8001. Start it with make serve.")

    session = rest("post", "/api/master/sessions", {"world_name": "sword_vale", "lang": "en"})
    sid = str(session["session_id"])
    try:
        player = rest(
            "post",
            f"/api/player/sessions/{sid}/character",
            {
                "name": "Anchor",
                "race": "human",
                "char_class": "fighter",
                "start_location": "silverport_city_tavern",
                "ability_scores": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
            },
        )
        location = str(player["location_id"])
        rest(
            "post",
            f"/api/master/sessions/{sid}/creatures",
            {
                "id": "live_npc",
                "name": "Live Witness",
                "entity_type": "npc",
                "start_location": location,
                "role": "guard",
                "personality": "Protective and observant",
                "hp": 60,
                "ac": 15,
                "speed": 30,
                "ai": "rule_based",
            },
        )
        brain = rest("put", f"/api/master/sessions/{sid}/creatures/live_npc/brain", {"type": "llm"})
        if brain.get("brain_type") != "llm":
            skipped("Server did not configure LlmBrain; check its OPENROUTER_API_KEY and LLM_MODEL environment.")
        rest(
            "put",
            f"/api/master/sessions/{sid}/creatures/live_npc/inner-self/core",
            {
                "relations": [{"target_id": str(player["player_id"]), "type": "loyal_to", "intensity": 80}],
                "mood": "alerted",
                "goals": [
                    {"kind": "typed", "type": "protect", "target_id": str(player["player_id"]), "status": "active"}
                ],
            },
        )
        before = snapshot(sid, "Before combat")
        drive_player(sid)
        after_combat = snapshot(sid, "After combat")
        rest(
            "patch",
            f"/api/master/sessions/{sid}/creatures/{player['player_id']}",
            {"location_id": "silverport_city"},
        )
        rest("post", f"/api/master/sessions/{sid}/time/advance", {"hours": 1})
        after_anchor = snapshot(sid, "After anchor leaves / dormancy boundary")
        report(before, after_combat, after_anchor)
    finally:
        try:
            rest("delete", f"/api/master/sessions/{sid}")
        except (RuntimeError, requests.RequestException) as error:
            print(f"WARN: cleanup failed for {sid}: {error}")


if __name__ == "__main__":
    main()
