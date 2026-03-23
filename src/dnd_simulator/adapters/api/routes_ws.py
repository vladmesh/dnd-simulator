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
import json
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.i18n import _

logger = logging.getLogger("dnd_simulator.ws")

router = APIRouter(tags=["websocket"])


# ---------------------------------------------------------------------------
# Text command → Action parser (mirrors CLI adapter logic)
# ---------------------------------------------------------------------------


def _parse_command(text: str) -> Action:
    """Parse a text command into an Action."""
    raw = text.strip()
    if not raw:
        return Action(name=ActionType.IDLE)
    cmd = raw.lower()

    if cmd in ("look", "status", "map"):
        return Action(name=ActionType.IDLE)

    if cmd.startswith("look "):
        target = raw[5:].strip()
        if target:
            return Action(name=ActionType.IDLE, params={"inspect_target": target})
        return Action(name=ActionType.IDLE)

    if cmd == "idle":
        return Action(name=ActionType.IDLE)

    if cmd in ("end_turn", "end"):
        return Action(name=ActionType.END_TURN)

    if cmd == "dodge":
        return Action(name=ActionType.DODGE)

    if cmd == "flee":
        return Action(name=ActionType.FLEE)

    if cmd == "wait" or cmd.startswith("wait "):
        parts = cmd.split()
        hours = 1
        if len(parts) > 1:
            try:
                hours = max(1, int(parts[1]))
            except ValueError:
                hours = 1
        return Action(name=ActionType.WAIT, params={"hours": hours})

    if cmd.startswith("say "):
        return Action(name=ActionType.SAY, params={"text": raw[4:].strip()})

    if cmd.startswith("attack "):
        target_id = raw[7:].strip().split()[0] if raw[7:].strip() else ""
        if target_id:
            return Action(name=ActionType.ATTACK, params={"target_id": target_id})
        return Action(name=ActionType.IDLE)

    if cmd.startswith("go "):
        target = raw[3:].strip()
        if target:
            return Action(name=ActionType.WAIT, params={"hours": 0, "travel_to": target})
        return Action(name=ActionType.IDLE)

    if cmd.startswith("move ") or cmd.startswith("dash "):
        is_dash = cmd.startswith("dash ")
        args = raw[5:].strip().split()
        if not args:
            return Action(name=ActionType.IDLE)
        params: dict[str, object] = {}
        keyword = args[0].lower()
        if keyword == "toward" and len(args) > 1:
            params["toward"] = args[1]
        elif keyword == "away" and len(args) > 1:
            params["away_from"] = args[1]
        else:
            params["direction"] = keyword
        return Action(name=ActionType.DASH if is_dash else ActionType.MOVE, params=params)

    return Action(name=ActionType.IDLE)


# ---------------------------------------------------------------------------
# WS event listener — bridges session events to a WebSocket connection
# ---------------------------------------------------------------------------


class WsEventListener:
    """Bridges GameSession events to a WebSocket client.

    All on_* methods are called from the Round thread.
    Uses asyncio.run_coroutine_threadsafe to marshal sends to the event loop.
    """

    def __init__(self, ws: WebSocket, loop: asyncio.AbstractEventLoop) -> None:
        self._ws = ws
        self._loop = loop

    def _send(self, msg: dict[str, Any]) -> None:
        if self._loop.is_closed():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._ws.send_json(msg), self._loop)
            future.result(timeout=30)
        except Exception:
            pass  # WS closed — session will remove this listener

    def on_turn(self, msg: dict[str, Any]) -> None:
        self._send(msg)

    def on_action_result(self, msg: dict[str, Any]) -> None:
        self._send(msg)

    def on_round_result(self, msg: dict[str, Any]) -> None:
        self._send(msg)

    def on_game_over(self) -> None:
        self._send({"type": "game_over"})


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/api/ws/{session_id}")
async def websocket_game(ws: WebSocket, session_id: str, player_id: str | None = None) -> None:
    """WebSocket game loop for a session.

    Thin bridge: validates session, registers as listener, forwards actions.
    Round lifecycle is owned by GameSession.
    """
    # Origin check
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
        await ws.close(code=4004, reason="session_not_found")
        return

    player = session.get_player(player_id)
    if player is None:
        await ws.send_json({"type": "error", "message": _("No player in session")})
        await ws.close(code=4004, reason="no_player")
        return

    # Register WS as event listener
    listener = WsEventListener(ws, asyncio.get_running_loop())

    # Replay last turn BEFORE start_round: for reconnects the round is
    # already running and won't re-fire on_turn, so the client needs
    # the cached message.  For first connect _last_turn_msg is None.
    # Done here (not in add_listener) to avoid deadlock: run_coroutine_threadsafe
    # + future.result() from the event loop thread would block forever.
    last_turn = session.get_last_turn_msg()
    if last_turn is not None:
        await ws.send_json(last_turn)

    session.add_listener(listener)

    # Start round if not already running (idempotent)
    session.start_round(player)

    # Rate limiting: token bucket
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
                    name=ActionType(str(msg.get("name", "idle"))),
                    params=msg.get("params", {}),
                )
                session.submit_player_action(action)

            elif msg_type == "command":
                session.submit_player_action(_parse_command(str(msg.get("text", ""))))

            else:
                await ws.send_json({"type": "error", "message": _("Unknown message type: {}").format(msg_type)})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("WebSocket error in session %s", session_id)
    finally:
        session.remove_listener(listener)
        # Don't stop round — it lives with the session, not the WS connection
