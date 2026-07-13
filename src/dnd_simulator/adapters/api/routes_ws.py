"""WebSocket endpoint for real-time game interaction.

Protocol (action → awareness cycle):
    Server → Client:
        {"type": "turn", "mode": "peaceful|combat", "awareness": {...}, "events": [...],
         "budget": {...}, "player": {...}, "location": {...}}
        {"type": "action_result", "action": "...", "events": [...], "budget": {...}, "player": {...}}
        {"type": "round_result", "events": [...], "player": {...}}
        {"type": "error", "message": "..."}
        {"type": "game_over"}

    Client → Server:
        {"type": "action", "name": "attack", "params": {"target_id": "..."}}
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, cast

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketDisconnect as _StarletteDisconnect

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.i18n import _
from dnd_simulator.service.action_parsing import ActionParseError, parse_action
from dnd_simulator.service.session import GameSession

logger = structlog.get_logger(domain="transport")

router = APIRouter(tags=["websocket"])


def _parse_json_object_envelope(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse one recoverable client message into a JSON object envelope."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None, _("Invalid JSON")
    if not isinstance(parsed, dict):
        return None, _("JSON message must be an object")
    return cast(dict[str, Any], parsed), None


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
        except (TimeoutError, _StarletteDisconnect, ConnectionError):
            logger.debug("ws_send_failed")

    def on_turn(self, msg: dict[str, Any]) -> None:
        self._send(msg)

    def on_action_result(self, msg: dict[str, Any]) -> None:
        self._send(msg)

    def on_round_result(self, msg: dict[str, Any]) -> None:
        self._send(msg)

    def on_reaction(self, msg: dict[str, Any]) -> None:
        self._send(msg)

    def on_game_over(self) -> None:
        self._send({"type": "game_over"})


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


async def _run_spectator(ws: WebSocket, session: GameSession, session_id: str) -> None:
    """Read-only observe loop for a `?spectate=true` connection.

    Registers a spectator listener (never drives the round, never counts toward the
    session-empty decision), replays the last turn on connect, and rejects any
    `action`/`reaction` the client sends. The receive loop exists only to detect
    disconnect; on exit the spectator is removed without ever evicting the session.
    """
    listener = WsEventListener(ws, asyncio.get_running_loop())

    # Replay last turn so a mid-session joiner sees current state immediately.
    last_turn = session.get_last_turn_msg()
    if last_turn is not None:
        await ws.send_json(last_turn)

    session.add_spectator(listener)

    # Rate limiting: token bucket (same shape as the player path)
    rl_budget = 20.0
    rl_last = time.monotonic()
    rl_max_burst = 20.0
    rl_per_sec = 5.0

    try:
        while True:
            raw = await ws.receive_text()

            now = time.monotonic()
            rl_budget = min(rl_max_burst, rl_budget + (now - rl_last) * rl_per_sec)
            rl_last = now
            if rl_budget < 1.0:
                await ws.send_json({"type": "error", "message": _("Rate limited, slow down")})
                continue
            rl_budget -= 1.0

            msg, parse_error = _parse_json_object_envelope(raw)
            if parse_error is not None:
                await ws.send_json({"type": "error", "message": parse_error})
                continue
            assert msg is not None
            msg_type = msg.get("type")

            if msg_type in ("action", "reaction"):
                await ws.send_json({"type": "error", "message": _("Spectators cannot submit actions")})
            else:
                await ws.send_json({"type": "error", "message": _("Unknown message type: {}").format(msg_type)})

    except WebSocketDisconnect:
        logger.info("ws_spectator_disconnected", session_id=session_id)
    except Exception:
        logger.exception("ws_spectator_error", session_id=session_id)
    finally:
        # Symmetric with the player path's to_thread, though remove_spectator never
        # joins the round thread because a spectator leaving never stops the round.
        await asyncio.to_thread(session.remove_spectator, listener)


@router.websocket("/api/ws/{session_id}")
async def websocket_game(ws: WebSocket, session_id: str, player_id: str | None = None, spectate: bool = False) -> None:
    """WebSocket game loop for a session.

    Thin bridge: validates session, registers as listener, forwards actions.
    Round lifecycle is owned by GameSession. With `?spectate=true` the connection
    is a read-only observer (no player, no start_round, actions rejected).
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
    logger.info("ws_connected", session_id=session_id, player_id=player_id, spectate=spectate)
    service = get_service()

    # Validate session
    try:
        session = service.get_session(session_id)
    except ValueError:
        await ws.send_json({"type": "error", "message": _("Session '{}' not found").format(session_id)})
        await ws.close(code=4004, reason="session_not_found")
        return

    # Spectator branch: read-only, no player resolution, no start_round.
    if spectate:
        await _run_spectator(ws, session, session_id)
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

            msg, parse_error = _parse_json_object_envelope(raw)
            if parse_error is not None:
                await ws.send_json({"type": "error", "message": parse_error})
                continue
            assert msg is not None
            msg_type = msg.get("type")

            if msg_type == "action":
                try:
                    action = parse_action(msg, default_name="idle")
                except ActionParseError as err:
                    await ws.send_json({"type": "error", "message": _("Unknown action: {}").format(err.name)})
                    continue
                session.submit_player_action(action)
            elif msg_type == "reaction":
                try:
                    action = parse_action(msg, default_name="skip")
                except ActionParseError as err:
                    await ws.send_json({"type": "error", "message": _("Unknown reaction: {}").format(err.name)})
                    continue
                session.submit_player_reaction(action)
            else:
                await ws.send_json({"type": "error", "message": _("Unknown message type: {}").format(msg_type)})

    except WebSocketDisconnect:
        logger.info("ws_disconnected", session_id=session_id)
    except Exception:
        logger.exception("ws_error", session_id=session_id)
    finally:
        # remove_listener may call stop_round(), which joins the round thread. That
        # thread can be blocked in _send (run_coroutine_threadsafe awaiting this loop),
        # so a blocking join on the event loop thread would deadlock until the join
        # times out, freezing all sessions. Run it in a worker thread so the loop stays
        # free to drain the round thread's pending send.
        await asyncio.to_thread(session.remove_listener, listener)
