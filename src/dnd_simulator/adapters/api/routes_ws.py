"""WebSocket endpoint for real-time game interaction.

Protocol (action → awareness cycle only, no queries):
    Server → Client:
        {"type": "turn", "mode": "peaceful|combat", "awareness": {...}, "events": [...], "budget": {...}}
        {"type": "action_result", "action": "...", "events": [...], "budget": {...}}
        {"type": "round_result", "events": [...]}
        {"type": "error", "message": "..."}
        {"type": "game_over"}

    Client → Server:
        {"type": "action", "name": "attack", "params": {"target_id": "..."}}
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import threading
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.core.action import Action
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.round import Round
from dnd_simulator.service.session import GameSession

logger = logging.getLogger("dnd_simulator.ws")

router = APIRouter(tags=["websocket"])


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


@router.websocket("/api/ws/{session_id}")
async def websocket_game(ws: WebSocket, session_id: str) -> None:
    """WebSocket game loop for a session.

    Expects the session to already exist (created via REST POST /api/master/sessions).
    Wires a PlayerBrain, starts Round in a background thread, and bridges
    WS messages to the game loop.
    """
    await ws.accept()
    service = get_service()

    # Validate session and player
    try:
        session = service.get_session(session_id)
    except ValueError:
        await ws.send_json({"type": "error", "message": f"Session '{session_id}' not found"})
        await ws.close()
        return

    player = session.get_player()
    if player is None:
        await ws.send_json({"type": "error", "message": "No player in session"})
        await ws.close()
        return
    entities_layer = _get_entities_layer(session)
    loop = asyncio.get_running_loop()

    # Wire PlayerBrain with queue pattern
    brain = PlayerBrain()

    def _ws_send_from_thread(msg: dict[str, Any]) -> None:
        """Send a WS message from Round thread. Silently ignores closed connections."""
        if loop.is_closed():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(ws.send_json(msg), loop)
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
        }
        if awareness.turn_budget is not None:
            msg["budget"] = _budget_to_dict(awareness.turn_budget)
        _ws_send_from_thread(msg)

    brain.set_on_turn(on_turn)
    player.brain = brain

    # Create Round with callbacks
    game_round = Round(session.world, entities_layer)

    def on_action(creature: Creature, action: Action, budget: TurnBudget) -> None:
        """Send action_result after each action within a turn."""
        if creature.id != player.id:
            return  # only send action_result for the player
        perceived = entities_layer.get_perceived_events(player)
        msg: dict[str, Any] = {
            "type": "action_result",
            "action": action.name,
            "events": _events_to_list(perceived),
            "budget": _budget_to_dict(budget),
        }
        _ws_send_from_thread(msg)

    game_round.set_on_action(on_action)

    def on_round_end(result: object) -> None:
        """Send perceived events after each round completes."""
        perceived = entities_layer.get_perceived_events(player)
        msg: dict[str, Any] = {
            "type": "round_result",
            "events": _events_to_list(perceived),
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
        if not loop.is_closed():
            try:
                future = asyncio.run_coroutine_threadsafe(ws.send_json({"type": "game_over"}), loop)
                future.result(timeout=5)
            except Exception:
                pass

    round_thread = threading.Thread(target=run_round_loop, daemon=True, name=f"round-{session_id}")
    round_thread.start()

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "action":
                action = Action(
                    name=str(msg.get("name", "idle")),
                    params=msg.get("params", {}),
                )
                brain.submit_action(action)

            else:
                await ws.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("WebSocket error in session %s", session_id)
    finally:
        # Clean shutdown: stop Round thread
        game_round.stop()
        brain.submit_action(Action(name="end_turn"))  # unblock queue
        round_thread.join(timeout=5)


def _get_entities_layer(session: GameSession) -> EntitiesLayer:
    """Find EntitiesLayer in session's world."""
    for layer in session.world.layers:
        if isinstance(layer, EntitiesLayer):
            return layer
    raise RuntimeError("EntitiesLayer not found")
