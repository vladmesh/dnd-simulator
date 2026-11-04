"""Regression coverage for session lifecycle edges and queued abstract movement."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import structlog
from test_region_encounters import _entities, _session_with_player
from test_session_lifecycle import RecordingListener

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.character import Character
from dnd_simulator.service.session import GameSession


@pytest.fixture
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GameSession]:
    monkeypatch.setenv("DND_WORLD_SEED", "42")
    monkeypatch.setenv("DND_DICE_SEED", "42")
    game_session = _session_with_player(tmp_path, "forest_edge")
    game_session._evict_grace_seconds = 3600
    try:
        yield game_session
    finally:
        game_session.stop_round()


def test_disconnect_replaces_outstanding_eviction_timer(session: GameSession) -> None:
    listener = RecordingListener()
    session.add_listener(listener)
    evicted: list[GameSession] = []
    session._on_empty = evicted.append
    previous = threading.Timer(3600, evicted.append, args=(session,))
    previous.daemon = True
    session._evict_timer = previous
    previous.start()
    replacement: threading.Timer | None = None
    try:
        session.remove_listener(listener)
        replacement = session._evict_timer

        assert replacement is not None
        assert replacement is not previous
        assert previous.finished.is_set()
        assert not session.has_player_listeners()
        assert evicted == []

        replacement.cancel()
        replacement.join(timeout=2)
        replacement.function(*replacement.args, **replacement.kwargs)

        assert evicted == [session]
        assert session._evict_timer is None
    finally:
        previous.cancel()
        previous.join(timeout=2)
        if replacement is not None:
            replacement.cancel()
            replacement.join(timeout=2)


class _DisconnectingListener(RecordingListener):
    def __init__(self, session: GameSession, departing: RecordingListener) -> None:
        super().__init__()
        self.session = session
        self.departing = departing
        self.turn_seen = threading.Event()

    def on_turn(self, msg: dict[str, Any]) -> None:
        super().on_turn(msg)
        self.session.remove_listener(self.departing)
        self.turn_seen.set()


def test_listener_removed_during_turn_broadcast_receives_no_stale_turn(session: GameSession) -> None:
    player = session.get_player()
    assert player is not None
    departing = RecordingListener()
    remaining = _DisconnectingListener(session, departing)
    session.add_listener(remaining)
    session.add_listener(departing)

    session.start_round(player)
    assert remaining.turn_seen.wait(timeout=2), "player turn was not broadcast"
    session.stop_round()

    assert departing.calls == []
    assert remaining.calls == [("on_turn", (session.get_last_turn_msg(),))]
    assert session.get_last_turn_msg() is not None
    assert session.has_player_listeners()
    assert session._evict_timer is None


@pytest.mark.parametrize("activation_fails", [False, True], ids=["natural-end", "activation-error"])
def test_round_loop_exit_notifies_game_over(
    session: GameSession, monkeypatch: pytest.MonkeyPatch, activation_fails: bool
) -> None:
    player = session.get_player()
    assert player is not None
    listener = RecordingListener()
    session.add_listener(listener)
    if activation_fails:

        def fail_activation(*args: object, **kwargs: object) -> None:
            raise RuntimeError("activation failed")

        monkeypatch.setattr(_entities(session), "update_activation", fail_activation)
    else:
        player.take_damage(player.current_hp)

    with structlog.testing.capture_logs() as logs:
        game_round = session.start_round(player)
        thread = session._round_thread
        assert thread is not None
        thread.join(timeout=2)

    assert not thread.is_alive()
    assert not game_round.is_stopped
    assert listener.calls[-1] == ("on_game_over", ())
    assert [method for method, _ in listener.calls] == (
        ["on_game_over"] if activation_fails else ["on_round_result", "on_game_over"]
    )
    errors = [event for event in logs if event.get("event") == "round_loop_error"]
    if activation_fails:
        assert len(errors) == 1
        assert "RuntimeError: activation failed" in errors[0]["traceback"]
        assert "fail_activation" in errors[0]["traceback"]
    else:
        assert errors == []


@pytest.mark.parametrize(("relation", "direction"), [("toward", "east"), ("away_from", "west")])
def test_submit_abstract_move_queues_concrete_direction(session: GameSession, relation: str, direction: str) -> None:
    player = session.get_player()
    assert player is not None
    player.active = True
    player.combat_position = (20, 20)
    target = Character(
        id="target",
        name="Target",
        location_id=player.location_id,
        active=True,
        combat_position=(40, 20),
    )
    entities = _entities(session)
    entities.add_entity(target)
    combat = entities._combat.start_combat(player.location_id)
    assert combat is not None
    brain = PlayerBrain()
    session._player_brain = brain
    action = Action(name=ActionType.MOVE, params={relation: target.id, "ft": 10})

    session.submit_player_action(action)
    brain.submit_action(Action(name=ActionType.SKIP))
    awareness = entities.build_awareness(player, session.world.time, session.world.make_query_fn("entities"))
    queued = brain.choose_action(player, awareness, [])

    assert queued == Action(name=ActionType.MOVE, params={"direction": direction, "ft": 10})
    assert action.params == {relation: target.id, "ft": 10}
