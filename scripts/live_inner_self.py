#!/usr/bin/env python3
"""Run the manual real-model inner-self scenario against ``make serve``.

Export OPENROUTER_API_KEY and LLM_MODEL in both the server and this shell.
Start the server with LOG_LEVEL=DEBUG LOG_DIR=./logs, export
DND_LIVE_LOG=./logs (the log directory), then run ``make live-inner-self``.
The script never prints the API key and never starts a server.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
from typing import Never, Protocol

import requests
import websocket  # type: ignore[import-untyped]

from dnd_simulator.live_inner_self_report import classify_report, parse_session_jsonl

BASE = "http://localhost:8001"
WS_BASE = "ws://localhost:8001"
DRIVE_DEADLINE_SECONDS = 90.0


class WebSocketConnection(Protocol):
    def send(self, payload: str) -> object: ...
    def recv(self) -> str: ...
    def close(self) -> object: ...


class Transport(Protocol):
    def request(self, method: str, path: str, body: object | None = None) -> dict[str, object]: ...
    def connect(self, session_id: str, player_id: str) -> WebSocketConnection: ...


class ScenarioDeadlineError(RuntimeError):
    """The driver used its entire wall-clock budget."""


@dataclass
class ScenarioResult:
    session_id: str
    before: dict[str, object] = field(default_factory=dict)
    after_combat: dict[str, object] = field(default_factory=dict)
    after_anchor: dict[str, object] = field(default_factory=dict)
    metrics: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    completed: bool = False

    @property
    def exit_code(self) -> int:
        return 0 if self.completed else 1


class HttpTransport:
    def __init__(self, base_url: str, ws_base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._ws_base_url = ws_base_url.rstrip("/")

    def request(self, method: str, path: str, body: object | None = None) -> dict[str, object]:
        response = requests.request(method, f"{self._base_url}{path}", json=body, timeout=20)
        try:
            data = response.json()
        except ValueError:
            data = {"detail": response.text}
        if not response.ok:
            raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {data}")
        if not isinstance(data, dict):
            raise RuntimeError(f"{method} {path}: expected JSON object")
        return data

    def connect(self, session_id: str, player_id: str) -> WebSocketConnection:
        return websocket.create_connection(f"{self._ws_base_url}/api/ws/{session_id}?player_id={player_id}", timeout=10)


def section(title: str, output: Callable[[str], None] = print) -> None:
    output(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def skipped(message: str) -> Never:
    print(f"SKIPPED / NOT RUNNABLE: {message}")
    raise SystemExit(2)


def _read_metrics(log_dir: Path | None, session_id: str) -> dict[str, object]:
    if log_dir is None:
        return {"available": False, "reason": "Set DND_LIVE_LOG to the server LOG_DIR directory."}
    path = log_dir / f"session_{session_id}" / "full.jsonl"
    try:
        return parse_session_jsonl(path.read_text(encoding="utf-8").splitlines(), session_id)
    except OSError as error:
        return {"available": False, "reason": f"Cannot read current session full.jsonl: {error}"}


def _snapshot(transport: Transport, session_id: str, label: str, output: Callable[[str], None]) -> dict[str, object]:
    state = transport.request("get", f"/api/master/sessions/{session_id}/creatures/live_npc/inner-self")
    section(label, output)
    output(json.dumps(state, ensure_ascii=False, indent=2, default=str))
    return state


def _recv_before_deadline(ws: WebSocketConnection, deadline: float) -> dict[str, object]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ScenarioDeadlineError("scenario deadline elapsed while waiting for a WebSocket message")
    received: Queue[object] = Queue(maxsize=1)

    def receive() -> None:
        try:
            received.put(ws.recv())
        except Exception as error:
            received.put(error)

    thread = threading.Thread(target=receive, daemon=True)
    thread.start()
    thread.join(remaining)
    if thread.is_alive():
        ws.close()
        raise ScenarioDeadlineError("scenario deadline elapsed while waiting for a WebSocket message")
    raw = received.get_nowait()
    if isinstance(raw, Exception):
        raise raw
    message = json.loads(raw)
    if not isinstance(message, dict):
        raise RuntimeError("WebSocket message was not an object")
    return message


def _wait_for_turn(ws: WebSocketConnection, deadline: float) -> None:
    while True:
        if _recv_before_deadline(ws, deadline).get("type") == "turn":
            return


def _drive_player(ws: WebSocketConnection, deadline: float) -> None:
    """Create one combat exchange while retaining the player listener."""
    _wait_for_turn(ws, deadline)
    for action in (
        {"type": "action", "name": "attack", "params": {"target_id": "live_npc"}},
        {"type": "action", "name": "flee", "params": {}},
    ):
        ws.send(json.dumps(action))
        _wait_for_turn(ws, deadline)


def _record_departure_event(ws: WebSocketConnection, deadline: float) -> None:
    """Leave one observed event for the anchor-departure digest boundary."""
    ws.send(json.dumps({"type": "action", "name": "say", "params": {"text": "I am leaving the tavern."}}))
    _wait_for_turn(ws, deadline)


def _core_payload(player_id: str) -> dict[str, object]:
    return {
        "relations": [{"target_id": player_id, "type": "loyal_to", "intensity": 80}],
        "mood": "alerted",
        "goals": [{"kind": "typed", "type": "protect", "target_id": player_id, "status": "active"}],
    }


def run_scenario(
    transport: Transport,
    *,
    log_dir: Path | None,
    deadline_seconds: float = DRIVE_DEADLINE_SECONDS,
    output: Callable[[str], None] = print,
) -> ScenarioResult:
    """Run the REST/WebSocket scenario and always produce a result plus cleanup."""
    session = transport.request("post", "/api/master/sessions", {"world_name": "sword_vale", "lang": "en"})
    session_id = str(session["session_id"])
    result = ScenarioResult(session_id=session_id)
    deadline = time.monotonic() + deadline_seconds
    try:
        player = transport.request(
            "post",
            f"/api/player/sessions/{session_id}/character",
            {
                "name": "Anchor",
                "race": "human",
                "char_class": "fighter",
                "fighting_style": "defense",
                "start_location": "silverport_city_tavern",
                "ability_scores": {"str": 15, "dex": 12, "con": 14, "int": 13, "wis": 10, "cha": 8},
            },
        )
        player_id = str(player["player_id"])
        location = str(player["location_id"])
        # The stock Sword Vale tavern contains Marta. The scenario needs its own
        # two-creature combat so another NPC cannot keep the scene in combat.
        transport.request("delete", f"/api/master/sessions/{session_id}/creatures/marta")
        transport.request(
            "post",
            f"/api/master/sessions/{session_id}/creatures",
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
        brain = transport.request("put", f"/api/master/sessions/{session_id}/creatures/live_npc/brain", {"type": "llm"})
        if brain.get("brain_type") != "llm":
            raise RuntimeError("server did not configure LlmBrain")
        transport.request(
            "put", f"/api/master/sessions/{session_id}/creatures/live_npc/inner-self/core", _core_payload(player_id)
        )
        result.before = _snapshot(transport, session_id, "Before combat", output)
        ws = transport.connect(session_id, player_id)
        try:
            _drive_player(ws, deadline)
            result.after_combat = _snapshot(transport, session_id, "After combat", output)
            _record_departure_event(ws, deadline)
            transport.request(
                "patch", f"/api/master/sessions/{session_id}/creatures/{player_id}", {"location_id": "silverport_city"}
            )
            transport.request(
                "put", f"/api/master/sessions/{session_id}/creatures/live_npc/activation", {"override": "dormant"}
            )
            result.after_anchor = _snapshot(transport, session_id, "After anchor leaves / dormancy boundary", output)
            result.completed = True
        finally:
            ws.close()
    except Exception as error:
        result.warnings.append(str(error) or type(error).__name__)
        partial_snapshots = (
            ("After combat (partial)", "after_combat"),
            ("After anchor leaves (partial)", "after_anchor"),
        )
        for label, attr in partial_snapshots:
            if getattr(result, attr):
                continue
            try:
                setattr(result, attr, _snapshot(transport, session_id, label, output))
            except Exception as snapshot_error:
                result.warnings.append(f"{label} snapshot failed: {snapshot_error}")
    finally:
        result.metrics = _read_metrics(log_dir, session_id)
        section("Real-model assumptions", output)
        output(json.dumps(result.metrics, ensure_ascii=False, indent=2, default=str))
        for warning in result.warnings:
            output(f"WARN: {warning}")
        for check in classify_report(
            result.before, result.after_combat, result.after_anchor, result.metrics, completed=result.completed
        ):
            output(f"{check['status']}: {check['name']}")
        try:
            transport.request("delete", f"/api/master/sessions/{session_id}")
        except Exception as error:
            result.warnings.append(f"cleanup failed: {error}")
            result.completed = False
    return result


def main() -> None:
    if not os.getenv("OPENROUTER_API_KEY") or not os.getenv("LLM_MODEL"):
        skipped("OPENROUTER_API_KEY and LLM_MODEL must be exported for this real-model scenario.")
    transport = HttpTransport(BASE, WS_BASE)
    try:
        requests.get(f"{BASE}/health", timeout=3).raise_for_status()
    except requests.RequestException:
        skipped("Server is not running at http://localhost:8001. Start it with make serve.")
    log_dir = Path(os.environ["DND_LIVE_LOG"]) if os.getenv("DND_LIVE_LOG") else None
    raise SystemExit(run_scenario(transport, log_dir=log_dir).exit_code)


if __name__ == "__main__":
    main()
