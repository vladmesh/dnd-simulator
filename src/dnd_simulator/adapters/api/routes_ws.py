"""WebSocket endpoint for real-time game interaction.

Protocol (action → awareness cycle, no separate queries):
    Server → Client:
        {"type": "turn", "mode": "peaceful|combat", "awareness": {...}, "events": [...],
         "budget": {...}, "player": {...}, "location": {...}}
        {"type": "action_result", "action": "...", "events": [...], "budget": {...}, "player": {...}}
        {"type": "round_result", "events": [...], "player": {...}}
        {"type": "error", "message": "..."}
        {"type": "game_over"}

    Client → Server:
        {"type": "action", "name": "attack", "params": {"target_id": "..."}}
        {"type": "command", "text": "attack goblin_1"}
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import threading
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.core.action import Action
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.character import Ability, Creature
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.i18n import _
from dnd_simulator.round import Round
from dnd_simulator.service.session import GameSession

logger = logging.getLogger("dnd_simulator.ws")

router = APIRouter(tags=["websocket"])


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _awareness_to_dict(awareness: PeacefulAwareness | CombatAwareness) -> dict[str, Any]:
    """Serialize awareness dataclass to JSON-friendly dict."""
    return dataclasses.asdict(awareness)


def _events_to_list(events: list[PerceivedEvent]) -> list[dict[str, Any]]:
    """Serialize perceived events to JSON-friendly list."""
    result: list[dict[str, Any]] = []
    for e in events:
        d = dataclasses.asdict(e)
        d["event_type"] = e.event_type.value
        result.append(d)
    return result


def _budget_to_dict(budget: TurnBudget) -> dict[str, Any]:
    """Serialize turn budget to JSON-friendly dict."""
    return dataclasses.asdict(budget)


def _player_to_dict(player: PlayerCharacter) -> dict[str, Any]:
    """Serialize player stats for the status panel."""
    scores = player.ability_scores
    return {
        "player_id": player.id,
        "name": player.name,
        "race": player.race.value,
        "char_class": player.char_class.value,
        "level": player.level,
        "alignment": player.alignment.value,
        "hp": player.current_hp,
        "max_hp": player.max_hp,
        "ac": player.ac,
        "gold": player.gold,
        "location_id": player.location_id,
        "ability_scores": {
            "str": scores[Ability.STR],
            "dex": scores[Ability.DEX],
            "con": scores[Ability.CON],
            "int": scores[Ability.INT],
            "wis": scores[Ability.WIS],
            "cha": scores[Ability.CHA],
        },
    }


def _location_data(session: GameSession, location_id: str) -> dict[str, Any]:
    """Build location + paths data for the map panel."""
    graph = session.world.location_graph
    if not graph.has(location_id):
        return {"current_location": location_id, "paths": []}

    loc = graph.get(location_id)
    paths = []
    for edge in loc.edges:
        target = graph.get(edge.target_id) if graph.has(edge.target_id) else None
        paths.append(
            {
                "target_id": edge.target_id,
                "target_name": target.name if target else edge.target_id,
                "distance_m": edge.distance_m,
            }
        )

    return {
        "current_location": loc.name,
        "current_location_id": loc.id,
        "description": loc.description,
        "region_id": loc.region_id,
        "paths": paths,
    }


# ---------------------------------------------------------------------------
# Text command → Action parser (mirrors CLI adapter logic)
# ---------------------------------------------------------------------------


def _parse_command(text: str) -> Action:
    """Parse a text command into an Action.

    All commands become actions submitted to the brain — including
    informational ones like 'look' and 'status' which map to 'idle'
    (they don't cost budget but cycle the turn so the player gets
    fresh awareness).
    """
    raw = text.strip()
    if not raw:
        return Action(name="idle")
    cmd = raw.lower()

    # Informational commands — map to idle (costs nothing, but cycles turn
    # so the player gets updated awareness + player + location data)
    if cmd in ("look", "status", "map"):
        return Action(name="idle")

    if cmd == "idle":
        return Action(name="idle")

    if cmd in ("end_turn", "end"):
        return Action(name="end_turn")

    if cmd == "dodge":
        return Action(name="dodge")

    if cmd == "flee":
        return Action(name="flee")

    if cmd == "wait" or cmd.startswith("wait "):
        parts = cmd.split()
        hours = 1
        if len(parts) > 1:
            try:
                hours = max(1, int(parts[1]))
            except ValueError:
                hours = 1
        return Action(name="wait", params={"hours": hours})

    if cmd.startswith("say "):
        return Action(name="say", params={"text": raw[4:].strip()})

    if cmd.startswith("attack "):
        target_id = raw[7:].strip().split()[0] if raw[7:].strip() else ""
        if target_id:
            return Action(name="attack", params={"target_id": target_id})
        return Action(name="idle")

    if cmd.startswith("go "):
        target = raw[3:].strip()
        if target:
            return Action(name="wait", params={"hours": 0, "travel_to": target})
        return Action(name="idle")

    if cmd.startswith("move ") or cmd.startswith("dash "):
        is_dash = cmd.startswith("dash ")
        args = raw[5:].strip().split()
        if not args:
            return Action(name="idle")
        params: dict[str, object] = {}
        keyword = args[0].lower()
        if keyword == "toward" and len(args) > 1:
            params["toward"] = args[1]
        elif keyword == "away" and len(args) > 1:
            params["away_from"] = args[1]
        else:
            params["direction"] = keyword
        return Action(name="dash" if is_dash else "move", params=params)

    # Unknown — treat as idle
    return Action(name="idle")


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/api/ws/{session_id}")
async def websocket_game(ws: WebSocket, session_id: str, player_id: str | None = None) -> None:
    """WebSocket game loop for a session.

    Expects the session to already exist (created via REST POST /api/master/sessions).
    Wires a PlayerBrain, starts Round in a background thread, and bridges
    WS messages to the game loop.

    Query params:
        player_id: which player to control (optional — defaults to first player in session)
    """
    # Origin check: if WS_ALLOWED_ORIGINS is set, reject connections from other origins
    allowed_raw = os.getenv("WS_ALLOWED_ORIGINS", "")
    if allowed_raw:
        allowed_origins = [o.strip() for o in allowed_raw.split(",") if o.strip()]
        origin = ws.headers.get("origin", "")
        if origin not in allowed_origins:
            await ws.close(code=4003)
            return

    await ws.accept()
    service = get_service()

    # Validate session and player
    try:
        session = service.get_session(session_id)
    except ValueError:
        await ws.send_json({"type": "error", "message": _("Session '{}' not found").format(session_id)})
        await ws.close()
        return

    player = session.get_player(player_id)
    if player is None:
        await ws.send_json({"type": "error", "message": _("No player in session")})
        await ws.close()
        return
    event_loop = asyncio.get_running_loop()

    # Wire PlayerBrain with queue pattern
    brain = PlayerBrain()

    def _ws_send_from_thread(msg: dict[str, Any]) -> None:
        """Send a WS message from Round thread. Silently ignores closed connections."""
        if event_loop.is_closed():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(ws.send_json(msg), event_loop)
            future.result(timeout=30)
        except Exception:
            pass  # WS already closed — Round will stop soon via stop()

    def on_turn(
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> None:
        """Called from Round thread when it's the player's turn."""
        msg: dict[str, Any] = {
            "type": "turn",
            "mode": "combat" if isinstance(awareness, CombatAwareness) else "peaceful",
            "awareness": _awareness_to_dict(awareness),
            "events": _events_to_list(events),
            "player": _player_to_dict(player),
            "location": _location_data(session, player.location_id),
        }
        if awareness.turn_budget is not None:
            msg["budget"] = _budget_to_dict(awareness.turn_budget)
        _ws_send_from_thread(msg)

    brain.set_on_turn(on_turn)
    player.brain = brain

    # Create Round with callbacks
    game_round = Round(session.world)

    def on_action(creature: Creature, action: Action, budget: TurnBudget | None) -> None:
        """Send action_result after each action within a turn."""
        if creature.id != player.id:
            return  # only send action_result for the player
        perceived = game_round.get_perceived_events(player)
        msg: dict[str, Any] = {
            "type": "action_result",
            "action": action.name,
            "events": _events_to_list(perceived),
            "player": _player_to_dict(player),
        }
        if budget is not None:
            msg["budget"] = _budget_to_dict(budget)
        _ws_send_from_thread(msg)

    game_round.set_on_action(on_action)

    def on_round_end(result: object) -> None:
        """Send perceived events after each round completes."""
        perceived = game_round.get_perceived_events(player)
        msg: dict[str, Any] = {
            "type": "round_result",
            "events": _events_to_list(perceived),
            "player": _player_to_dict(player),
        }
        _ws_send_from_thread(msg)

    game_round.set_on_round_end(on_round_end)

    # Start Round loop in background thread
    def run_round_loop() -> None:
        try:
            game_round.run_loop()
        except Exception:
            logger.exception("Round loop error in session %s", session_id)
        # Signal game over (skip if loop is closed — WS already disconnected)
        if not event_loop.is_closed():
            try:
                future = asyncio.run_coroutine_threadsafe(ws.send_json({"type": "game_over"}), event_loop)
                future.result(timeout=5)
            except Exception:
                pass

    round_thread = threading.Thread(target=run_round_loop, daemon=True, name=f"round-{session_id}")
    round_thread.start()

    # Rate limiting: token bucket (burst 10, refill 2 msg/sec)
    rl_budget = 20.0
    rl_last = time.monotonic()
    rl_max_burst = 20.0
    rl_per_sec = 5.0

    try:
        while True:
            raw = await ws.receive_text()

            # Enforce rate limit
            now = time.monotonic()
            rl_budget = min(rl_max_burst, rl_budget + (now - rl_last) * rl_per_sec)
            rl_last = now
            if rl_budget < 1.0:
                await ws.send_json({"type": "error", "message": _("Rate limited, slow down")})
                continue
            rl_budget -= 1.0

            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "action":
                action = Action(
                    name=str(msg.get("name", "idle")),
                    params=msg.get("params", {}),
                )
                brain.submit_action(action)

            elif msg_type == "command":
                brain.submit_action(_parse_command(str(msg.get("text", ""))))

            else:
                await ws.send_json({"type": "error", "message": _("Unknown message type: {}").format(msg_type)})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("WebSocket error in session %s", session_id)
    finally:
        # Clean shutdown: stop Round thread
        game_round.stop()
        brain.submit_action(Action(name="end_turn"))  # unblock queue
        round_thread.join(timeout=5)
