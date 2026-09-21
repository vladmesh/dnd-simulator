"""Real-ASGI disconnect in the middle of a combat round: nothing is sent to the closed socket.

Reproduces the PO's `listener_error ... Unexpected ASGI message 'websocket.send' after
'websocket.close'` through FastAPI's TestClient websocket instead of a mocked socket.
"""

from __future__ import annotations

import threading
import time
from http import HTTPStatus
from pathlib import Path

import structlog
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

_SLOW_SECONDS = 0.5


class _SlowDodgeBrain(Brain):
    """Models an LLM NPC: blocks in its decision, then Dodges (an action broadcast to listeners)."""

    def __init__(self, entered: threading.Event) -> None:
        self._entered = entered

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        self._entered.set()
        time.sleep(_SLOW_SECONDS)
        return Action(name=ActionType.DODGE)


def test_closing_the_socket_mid_combat_round_logs_no_send_after_close(tmp_path: Path) -> None:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    set_service(service)
    client = TestClient(app)
    session_id = client.post("/api/master/sessions", json={"lang": "en"}).json()["session_id"]
    response = client.post(
        f"/api/player/sessions/{session_id}/character",
        json={
            "name": "Fighter",
            "race": "human",
            "char_class": "fighter",
            "ability_scores": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
        },
    )
    assert response.status_code == HTTPStatus.OK
    session = service.get_session(session_id)
    session._evict_grace_seconds = 3600
    player = session.get_player()
    assert player is not None
    entered = threading.Event()
    slow = Creature(id="slow", name="Slow", location_id=player.location_id, brain=_SlowDodgeBrain(entered))
    after = Creature(id="after", name="After", location_id=player.location_id, brain=_SlowDodgeBrain(threading.Event()))
    entities = session.world.get_layer(EntitiesLayer)
    entities.add_entity(slow)
    entities.add_entity(after)
    combat = CombatState(location_id=player.location_id, turn_order=[player.id, slow.id, after.id])
    entities._combat._combats[player.location_id] = combat

    with structlog.testing.capture_logs() as logs:
        with client.websocket_connect(f"/api/ws/{session_id}") as ws:
            while (message := ws.receive_json())["type"] != "turn":
                pass
            assert message["mode"] == "combat"
            ws.send_json({"type": "action", "name": "end_turn", "params": {}})
            assert entered.wait(timeout=5), "the slow NPC turn never started"
        # Leaving the block closes the socket while the NPC decision is still in flight.
        deadline = time.monotonic() + 5
        while session._round is not None and time.monotonic() < deadline:
            time.sleep(0.02)
        time.sleep(_SLOW_SECONDS)  # let the in-flight decision return and be discarded

    assert session._round is None
    events = [entry.get("event") for entry in logs]
    assert "listener_error" not in events
    assert "disconnect_stop_failed" not in events
    assert "stop_round_timeout" not in events
    assert not any("after" in str(entry.get("exc_info", "")) for entry in logs)
    assert not slow.is_dodging
    assert combat.resume_turn_index == 1
    client.delete(f"/api/master/sessions/{session_id}")
