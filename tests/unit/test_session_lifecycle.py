"""Characterization tests for GameSession lifecycle surface.

Pins the synchronous (no background thread) behaviour of listener dispatch,
submit-without-round guards, and the resolve_abstract_move resolver, the exact
code the next sprint's spectator-listener extends and Phase 2's GameService peel
could break silently. These describe current behaviour and pass on first run; a
failure means a real bug, not a missing feature.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.combat import Position
from dnd_simulator.core.world import World
from dnd_simulator.round import Round
from dnd_simulator.rules.movement import calculate_away_direction, calculate_direction
from dnd_simulator.service import GameService
from dnd_simulator.service.session import GameSession, resolve_abstract_move
from dnd_simulator.storage.store import SaveStore

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class RecordingListener:
    """Listener implementing SessionEventListener; records every method fired."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def on_turn(self, msg: dict[str, Any]) -> None:
        self.calls.append(("on_turn", (msg,)))

    def on_action_result(self, msg: dict[str, Any]) -> None:
        self.calls.append(("on_action_result", (msg,)))

    def on_round_result(self, msg: dict[str, Any]) -> None:
        self.calls.append(("on_round_result", (msg,)))

    def on_reaction(self, msg: dict[str, Any]) -> None:
        self.calls.append(("on_reaction", (msg,)))

    def on_game_over(self) -> None:
        self.calls.append(("on_game_over", ()))


class RaisingListener:
    """Listener whose on_turn raises, used to prove _fire isolates failures."""

    def __init__(self) -> None:
        self.called = False

    def on_turn(self, msg: dict[str, Any]) -> None:
        self.called = True
        raise RuntimeError("boom")

    def on_action_result(self, msg: dict[str, Any]) -> None:  # pragma: no cover - unused
        pass

    def on_round_result(self, msg: dict[str, Any]) -> None:  # pragma: no cover - unused
        pass

    def on_reaction(self, msg: dict[str, Any]) -> None:  # pragma: no cover - unused
        pass

    def on_game_over(self) -> None:  # pragma: no cover - unused
        pass


class _StubBattleMap:
    def __init__(self, positions: dict[str, Position]) -> None:
        self._positions = positions

    def get_position(self, entity_id: str) -> Position | None:
        return self._positions.get(entity_id)


class _StubCombat:
    def __init__(self, battle_map: _StubBattleMap) -> None:
        self.battle_map = battle_map


class _StubHost:
    """Minimal CreatureHost for resolve_abstract_move; only get_combat is touched."""

    def __init__(self, combat: _StubCombat | None) -> None:
        self._combat = combat

    def get_combat(self, location_id: str) -> _StubCombat | None:
        return self._combat


class _StubMover:
    def __init__(self, mover_id: str = "mover", location_id: str = "loc") -> None:
        self.id = mover_id
        self.location_id = location_id


def _session() -> GameSession:
    """A session with a mock world, enough for listener/submit tests (no round)."""
    return GameSession(session_id="test", world=MagicMock(spec=World))


# ---------------------------------------------------------------------------
# Listener dispatch
# ---------------------------------------------------------------------------


class TestListenerDispatch:
    def test_fire_calls_every_listener(self) -> None:
        session = _session()
        a = RecordingListener()
        b = RecordingListener()
        session.add_listener(a)
        session.add_listener(b)

        msg = {"x": 1}
        session._fire("on_turn", msg)

        assert a.calls == [("on_turn", (msg,))]
        assert b.calls == [("on_turn", (msg,))]

    def test_raising_listener_does_not_block_others(self) -> None:
        """A listener that raises is swallowed; later listeners still fire."""
        session = _session()
        raiser = RaisingListener()
        recorder = RecordingListener()
        # Register the raiser first so the recorder comes after it in iteration order.
        session.add_listener(raiser)
        session.add_listener(recorder)

        msg = {"y": 2}
        session._fire("on_turn", msg)  # must not propagate the RuntimeError

        assert raiser.called is True
        assert recorder.calls == [("on_turn", (msg,))]


class TestEmptyListeners:
    def test_removing_last_listener_fires_on_empty(self) -> None:
        """With no round running, removing the last listener calls _on_empty once."""
        session = _session()
        listener = RecordingListener()
        session.add_listener(listener)

        seen: list[GameSession] = []
        session._on_empty = lambda s: seen.append(s)

        session.remove_listener(listener)

        assert seen == [session]

    def test_remove_unregistered_listener_is_noop(self) -> None:
        """Removing a listener that was never registered does not raise or drop others."""
        session = _session()
        registered = RecordingListener()
        session.add_listener(registered)

        fired: list[GameSession] = []
        session._on_empty = lambda s: fired.append(s)

        # Not registered: suppressed ValueError, existing listener untouched, not empty.
        session.remove_listener(RecordingListener())

        assert fired == []
        assert session._listeners == [registered]


class TestSpectatorListener:
    """Read-only spectators (Sprint 020 phase 3): receive the broadcast, never drive lifecycle."""

    def test_spectator_receives_broadcast(self) -> None:
        """A spectator gets the same events fired to player listeners."""
        session = _session()
        player = RecordingListener()
        spectator = RecordingListener()
        session.add_listener(player)
        session.add_spectator(spectator)

        msg = {"x": 1}
        session._fire("on_turn", msg)
        session._fire("on_action_result", msg)

        assert player.calls == [("on_turn", (msg,)), ("on_action_result", (msg,))]
        assert spectator.calls == [("on_turn", (msg,)), ("on_action_result", (msg,))]

    def test_spectator_added_after_player_receives_later_events(self) -> None:
        """Joining mid-stream, a spectator gets subsequent events (not the ones it missed)."""
        session = _session()
        player = RecordingListener()
        session.add_listener(player)
        session._fire("on_turn", {"first": 1})

        spectator = RecordingListener()
        session.add_spectator(spectator)
        session._fire("on_turn", {"second": 2})

        assert spectator.calls == [("on_turn", ({"second": 2},))]
        assert player.calls == [("on_turn", ({"first": 1},)), ("on_turn", ({"second": 2},))]

    def test_spectator_alone_is_player_empty(self) -> None:
        """A session with only spectators counts as player-empty (lifecycle keys on players)."""
        session = _session()
        session.add_spectator(RecordingListener())
        assert session.has_player_listeners() is False

    def test_player_present_has_player_listeners(self) -> None:
        session = _session()
        session.add_listener(RecordingListener())
        assert session.has_player_listeners() is True

    def test_remove_only_spectator_does_not_fire_on_empty(self) -> None:
        """Removing a spectator never triggers the empty handler, even with no players present."""
        session = _session()
        spectator = RecordingListener()
        session.add_spectator(spectator)

        fired: list[GameSession] = []
        session._on_empty = lambda s: fired.append(s)

        session.remove_spectator(spectator)

        assert fired == []

    def test_remove_spectator_keeps_player_in_broadcast(self) -> None:
        """After a spectator leaves, the remaining player listener still gets events."""
        session = _session()
        player = RecordingListener()
        spectator = RecordingListener()
        session.add_listener(player)
        session.add_spectator(spectator)

        session.remove_spectator(spectator)
        session._fire("on_turn", {"z": 9})

        assert player.calls == [("on_turn", ({"z": 9},))]

    def test_last_player_leaving_with_spectator_present_fires_on_empty(self) -> None:
        """The session is player-empty when the last player goes, even if a spectator remains."""
        session = _session()
        player = RecordingListener()
        spectator = RecordingListener()
        session.add_listener(player)
        session.add_spectator(spectator)

        seen: list[GameSession] = []
        session._on_empty = lambda s: seen.append(s)

        session.remove_listener(player)

        assert seen == [session]


# ---------------------------------------------------------------------------
# Submit guards (no round running)
# ---------------------------------------------------------------------------


class TestSubmitWithoutRound:
    def test_submit_action_raises_when_idle(self) -> None:
        session = _session()
        with pytest.raises(RuntimeError):
            session.submit_player_action(Action(name=ActionType.MOVE, params={"direction": "north", "ft": 5}))

    def test_submit_reaction_raises_when_idle(self) -> None:
        session = _session()
        with pytest.raises(RuntimeError):
            session.submit_player_reaction(Action(name=ActionType.OPPORTUNITY_ATTACK))


# ---------------------------------------------------------------------------
# resolve_abstract_move
# ---------------------------------------------------------------------------


class TestResolveAbstractMove:
    def test_toward_resolves_to_direction_and_ft(self) -> None:
        mover_pos = Position(10, 10)
        target_pos = Position(25, 10)  # due east of the mover
        host = _StubHost(_StubCombat(_StubBattleMap({"mover": mover_pos, "tgt": target_pos})))
        mover = _StubMover()
        action = Action(name=ActionType.MOVE, params={"toward": "tgt", "ft": 10})

        result = resolve_abstract_move(action, mover, host)  # type: ignore[arg-type]

        assert result.name == ActionType.MOVE
        assert result.params["direction"] == calculate_direction(mover_pos, target_pos)
        assert result.params["ft"] == 10

    def test_away_from_resolves_to_away_direction(self) -> None:
        mover_pos = Position(10, 10)
        target_pos = Position(25, 10)  # east, so "away" is west
        host = _StubHost(_StubCombat(_StubBattleMap({"mover": mover_pos, "tgt": target_pos})))
        mover = _StubMover()
        action = Action(name=ActionType.MOVE, params={"away_from": "tgt", "ft": 15})

        result = resolve_abstract_move(action, mover, host)  # type: ignore[arg-type]

        assert result.params["direction"] == calculate_away_direction(mover_pos, target_pos)
        assert result.params["ft"] == 15

    def test_no_combat_returns_action_unchanged(self) -> None:
        host = _StubHost(None)
        mover = _StubMover()
        action = Action(name=ActionType.MOVE, params={"toward": "tgt", "ft": 10})

        result = resolve_abstract_move(action, mover, host)  # type: ignore[arg-type]

        assert result is action

    def test_no_mover_position_returns_action_unchanged(self) -> None:
        # Battle map has the target but not the mover.
        host = _StubHost(_StubCombat(_StubBattleMap({"tgt": Position(25, 10)})))
        mover = _StubMover()
        action = Action(name=ActionType.MOVE, params={"toward": "tgt", "ft": 10})

        result = resolve_abstract_move(action, mover, host)  # type: ignore[arg-type]

        assert result is action

    def test_no_target_position_returns_action_unchanged(self) -> None:
        # Battle map has the mover but not the target.
        host = _StubHost(_StubCombat(_StubBattleMap({"mover": Position(10, 10)})))
        mover = _StubMover()
        action = Action(name=ActionType.MOVE, params={"toward": "tgt", "ft": 10})

        result = resolve_abstract_move(action, mover, host)  # type: ignore[arg-type]

        assert result is action


# ---------------------------------------------------------------------------
# Round lifecycle (live background thread)
# ---------------------------------------------------------------------------

_FIGHTER_DATA = {
    "name": "Thrain",
    "race": "dwarf",
    "class": "fighter",
    "alignment": "lawful_good",
    "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
    "fighting_style": "defense",
}


@pytest.fixture
def session_with_player() -> Any:
    """A real sword_vale session with a fighter; teardown always stops the round.

    PlayerBrain blocks on its queue, so a started round parks on the player's first
    turn and the thread stays alive without sleeps. Teardown's stop_round is a safe
    no-op when no round was started, so no test can leak a live thread.
    """
    service = GameService(store=MagicMock(spec=SaveStore))
    sid = service.start_game(world_name="sword_vale").session_id
    service.create_player(sid, _FIGHTER_DATA)
    session = service.get_session(sid)
    player = session.get_player()
    assert player is not None
    try:
        yield session, player
    finally:
        session.stop_round()


class TestStartRound:
    def test_start_returns_round_wires_brain_and_thread_alive(self, session_with_player: Any) -> None:
        session, player = session_with_player

        game_round = session.start_round(player)

        assert isinstance(game_round, Round)
        assert isinstance(player.brain, PlayerBrain)
        assert session._round_thread is not None
        assert session._round_thread.is_alive()

    def test_start_round_is_idempotent(self, session_with_player: Any) -> None:
        """A second start while the thread is alive returns the same Round, no 2nd thread."""
        session, player = session_with_player

        r1 = session.start_round(player)
        thread1 = session._round_thread
        r2 = session.start_round(player)

        assert r1 is r2
        assert session._round_thread is thread1

    def test_submit_after_start_does_not_raise(self, session_with_player: Any) -> None:
        session, player = session_with_player
        session.start_round(player)

        # Reaches the live brain (no RuntimeError); ends the parked player turn.
        session.submit_player_action(Action(name=ActionType.END_TURN))


class TestStopRound:
    def test_stop_clears_state_and_joins_thread(self, session_with_player: Any) -> None:
        session, player = session_with_player
        session.start_round(player)
        thread = session._round_thread
        assert thread is not None

        session.stop_round()

        assert session._round is None
        assert session._player_brain is None
        assert session._round_thread is None
        assert not thread.is_alive()

    def test_stop_when_idle_does_not_raise(self, session_with_player: Any) -> None:
        session, _player = session_with_player
        # No round started — stop_round must be a safe no-op.
        session.stop_round()
