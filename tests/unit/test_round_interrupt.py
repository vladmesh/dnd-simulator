"""A disconnect stops the round mid-round: no turn after it runs, nothing is replayed on resume.

Reproduces the PO acceptance defect of sprint 1451: closing the player's tab during a combat
round kept running the remaining creature turns (one of them a slow LLM decision) without a
listener, timed the stop out and beat the absent player. These tests drive a real
``GameSession`` round thread over a minimal world.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.round import Round
from dnd_simulator.service.session import GameSession

_SLOW_DECISION_SECONDS = 0.6


class _Recorder:
    """Shared turn log for every brain in a scenario."""

    def __init__(self) -> None:
        self.decisions: list[str] = []
        self.budgets: dict[str, list[TurnBudget | None]] = {}


class _SlowDodgeBrain(Brain):
    """Models an LLM NPC: the first decision blocks, then it Dodges; later decisions end the turn."""

    def __init__(self, recorder: _Recorder, entered: threading.Event, delay: float) -> None:
        self._recorder = recorder
        self._entered = entered
        self._delay = delay
        self.slow_calls = 0

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        self._recorder.decisions.append(creature.id)
        self._recorder.budgets.setdefault(creature.id, []).append(awareness.turn_budget)
        if self.slow_calls == 0:
            self.slow_calls += 1
            self._entered.set()
            time.sleep(self._delay)
            return Action(name=ActionType.DODGE)
        return END_TURN


class _RecordingEndTurnBrain(Brain):
    def __init__(self, recorder: _Recorder) -> None:
        self._recorder = recorder

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        self._recorder.decisions.append(creature.id)
        return END_TURN


class _Listener:
    """Records every event; fails loudly on any send after it was closed."""

    def __init__(self, on_turn: Any = None) -> None:
        self.calls: list[str] = []
        self.closed = False
        self.sends_after_close: list[str] = []
        self._on_turn = on_turn
        self.turns = threading.Semaphore(0)

    def _record(self, method: str) -> None:
        if self.closed:
            self.sends_after_close.append(method)
        self.calls.append(method)

    def on_turn(self, msg: dict[str, Any]) -> None:
        self._record("on_turn")
        if self._on_turn is not None:
            self._on_turn(msg)
        self.turns.release()

    def on_action_result(self, msg: dict[str, Any]) -> None:
        self._record("on_action_result")

    def on_round_result(self, msg: dict[str, Any]) -> None:
        self._record("on_round_result")

    def on_reaction(self, msg: dict[str, Any]) -> None:
        self._record("on_reaction")

    def on_game_over(self) -> None:
        self._record("on_game_over")


def _make_world(entities: list[Creature]) -> World:
    region = Region(
        id="r1",
        name="Test Field",
        terrain=TerrainType.PLAINS,
        latitude=45.0,
        longitude=0.0,
        elevation=100,
        water_proximity=0.0,
        connections=[],
    )
    settlements = SettlementsLayer(settlements=[], region_terrains={"r1": TerrainType.PLAINS})
    politics = PoliticsLayer(
        nations=[],
        region_terrains={"r1": TerrainType.PLAINS},
        region_adjacency={},
        region_income_fn=settlements.get_region_income,
    )
    return World(
        layers=[GeographyLayer(regions=[region]), politics, settlements, EntitiesLayer(entities=list(entities))],
        time=GameDateTime(year=1, month=1, day=1, hour=10),
        location_graph=LocationGraph([Location(id="r1", name="Test Field", region_id="r1")]),
    )


def _entities(world: World) -> EntitiesLayer:
    return next(layer for layer in world.layers if isinstance(layer, EntitiesLayer))


def _combat_session(turn_order_ids: list[str], creatures: list[Creature]) -> tuple[GameSession, CombatState]:
    world = _make_world(creatures)
    combat = CombatState(location_id="r1", turn_order=list(turn_order_ids))
    _entities(world)._combat._combats["r1"] = combat
    session = GameSession(session_id="interrupt", world=world, world_name="test")
    session._evict_grace_seconds = 3600
    return session, combat


def _player() -> PlayerCharacter:
    return PlayerCharacter(id="player", name="Player", location_id="r1", max_hp=200, current_hp=200)


class TestDisconnectDuringNpcTurns:
    def test_slow_npc_decision_is_discarded_and_later_turns_do_not_run(self) -> None:
        recorder = _Recorder()
        entered = threading.Event()
        slow_brain = _SlowDodgeBrain(recorder, entered, _SLOW_DECISION_SECONDS)
        slow = Creature(id="slow", name="Slow", location_id="r1", brain=slow_brain)
        slow.conditions[Condition.POISONED] = 3
        after = Creature(id="after", name="After", location_id="r1", brain=_RecordingEndTurnBrain(recorder))
        player = _player()
        session, combat = _combat_session([player.id, slow.id, after.id], [player, slow, after])

        listener = _Listener(on_turn=lambda _msg: session.submit_player_action(END_TURN))
        spectator = _Listener()
        session.add_spectator(spectator)
        session.add_listener(listener)
        session.start_round(player)
        thread = session._round_thread
        assert thread is not None
        assert entered.wait(timeout=5), "the slow NPC turn never started"
        spectator_calls_at_disconnect = len(spectator.calls)

        started = time.monotonic()
        listener.closed = True
        session.remove_listener(listener)
        elapsed = time.monotonic() - started

        # The only wait is the one in-flight decision; the rest of the round is not awaited.
        assert elapsed < _SLOW_DECISION_SECONDS + 0.5
        assert elapsed < session._round_stop_timeout_seconds
        assert not thread.is_alive()
        assert session._round is None
        # The late Dodge was not applied, no creature after it acted, time did not advance.
        assert recorder.decisions == [slow.id]
        assert not slow.is_dodging
        assert spectator.calls[spectator_calls_at_disconnect:] == []
        assert listener.sends_after_close == []
        assert player.current_hp == 200
        assert session.world.time == GameDateTime(year=1, month=1, day=1, hour=10)
        # The cursor names the interrupted, already started turn.
        assert combat.resume_turn_index == 1
        assert combat.resume_turn_started is True
        assert slow.conditions[Condition.POISONED] == 2
        budget_at_interrupt = slow.turn_budget

        # Reconnect: the slow NPC continues its started turn, then the next creature, then the player.
        reconnected = _Listener()
        session.add_listener(reconnected)
        session.start_round(player)
        assert reconnected.turns.acquire(timeout=5), "the player's next turn never came"
        try:
            assert recorder.decisions == [slow.id, slow.id, after.id]
            # Same turn, same budget: conditions were not ticked a second time.
            assert recorder.budgets[slow.id][1] == budget_at_interrupt
            assert slow.conditions[Condition.POISONED] == 2
            assert combat.round_number == 2
            assert player.current_hp == 200
        finally:
            reconnected.closed = True
            session.remove_listener(reconnected)
        assert reconnected.sends_after_close == []


class TestDisconnectDuringPlayerTurn:
    def test_waiting_player_turn_is_kept_and_resumed_not_ended(self) -> None:
        recorder = _Recorder()
        before = Creature(id="before", name="Before", location_id="r1", brain=_RecordingEndTurnBrain(recorder))
        after = Creature(id="after", name="After", location_id="r1", brain=_RecordingEndTurnBrain(recorder))
        player = _player()
        session, combat = _combat_session([before.id, player.id, after.id], [before, player, after])

        listener = _Listener()
        session.add_listener(listener)
        session.start_round(player)
        assert listener.turns.acquire(timeout=5)
        budget = player.turn_budget
        assert budget is not None
        budget.movement_remaining = 5  # the player already moved this turn

        started = time.monotonic()
        listener.closed = True
        session.remove_listener(listener)

        assert time.monotonic() - started < 1.0
        # The END_TURN injected to wake the waiting brain did not end the player's turn.
        assert recorder.decisions == [before.id]
        assert combat.resume_turn_index == 1
        assert combat.resume_turn_started is True
        assert listener.sends_after_close == []

        reconnected = _Listener(on_turn=lambda _msg: session.submit_player_action(END_TURN))
        session.add_listener(reconnected)
        session.start_round(player)
        try:
            assert reconnected.turns.acquire(timeout=5)
            # The same turn continues with the movement already spent — no fresh budget.
            assert player.turn_budget is not None
            assert player.turn_budget.movement_remaining == 5
            assert reconnected.turns.acquire(timeout=5)  # next round's player turn
            assert recorder.decisions == [before.id, after.id, before.id]
        finally:
            session.remove_listener(reconnected)


class TestInterruptedCombatSurvivesSaveLoad:
    def test_restored_cursor_continues_the_started_turn(self) -> None:
        recorder = _Recorder()
        entered = threading.Event()
        slow = Creature(
            id="slow", name="Slow", location_id="r1", brain=_SlowDodgeBrain(recorder, entered, _SLOW_DECISION_SECONDS)
        )
        slow.conditions[Condition.POISONED] = 3
        after = Creature(id="after", name="After", location_id="r1", brain=_RecordingEndTurnBrain(recorder))
        first = Creature(id="first", name="First", location_id="r1", brain=_RecordingEndTurnBrain(recorder))
        world = _make_world([first, slow, after])
        entities = _entities(world)
        entities._combat._combats["r1"] = CombatState(location_id="r1", turn_order=[first.id, slow.id, after.id])
        game_round = Round(world, entities)
        runner = threading.Thread(target=game_round.run_round)
        runner.start()
        assert entered.wait(timeout=5)
        game_round.stop()
        runner.join(timeout=5)
        assert not runner.is_alive()
        state = entities.get_state()

        restored_recorder = _Recorder()
        fresh_first = Creature(id="first", name="First", location_id="r1")
        fresh_slow = Creature(id="slow", name="Slow", location_id="r1")
        fresh_after = Creature(id="after", name="After", location_id="r1")
        restored_world = _make_world([fresh_first, fresh_slow, fresh_after])
        restored = _entities(restored_world)
        restored.load_state(state)
        for entity_id in ("first", "slow", "after"):
            creature = restored.get_entity(entity_id)
            assert isinstance(creature, Creature)
            creature.brain = _RecordingEndTurnBrain(restored_recorder)
        combat = restored.get_combat("r1")
        assert combat is not None
        assert combat.resume_turn_index == 1
        assert combat.resume_turn_started is True

        Round(restored_world, restored).run_round()

        restored_slow = restored.get_entity("slow")
        assert isinstance(restored_slow, Creature)
        assert restored_recorder.decisions == ["slow", "after"]
        assert restored_slow.conditions[Condition.POISONED] == 2
        assert combat.resume_turn_index is None
        assert combat.resume_turn_started is False


class TestPeacefulStop:
    def test_stop_skips_the_rest_of_the_peaceful_round_without_advancing_time(self) -> None:
        recorder = _Recorder()
        npc = Creature(id="npc", name="NPC", location_id="r1", brain=_RecordingEndTurnBrain(recorder))
        player = _player()
        world = _make_world([player, npc])
        session = GameSession(session_id="peaceful", world=world)
        session._evict_grace_seconds = 3600
        listener = _Listener()
        session.add_listener(listener)
        session.start_round(player)
        assert listener.turns.acquire(timeout=5)
        start_time = world.time

        started = time.monotonic()
        listener.closed = True
        session.remove_listener(listener)

        assert time.monotonic() - started < 1.0
        assert recorder.decisions == []
        assert world.time == start_time
        assert listener.sends_after_close == []


class TestWsListenerClose:
    def test_closed_listener_never_reaches_the_socket(self) -> None:
        import asyncio
        from unittest.mock import AsyncMock, MagicMock

        from dnd_simulator.adapters.api.routes_ws import WsEventListener

        ws = MagicMock()
        ws.send_json = AsyncMock()
        loop = asyncio.new_event_loop()
        runner = threading.Thread(target=loop.run_forever, daemon=True)
        runner.start()
        try:
            listener = WsEventListener(ws, loop)
            listener.on_turn({"type": "turn"})
            assert ws.send_json.await_count == 1

            # A send scheduled before close() but run on the loop after it is dropped too.
            pending = listener._send_if_open({"type": "late"})
            listener.close()
            asyncio.run_coroutine_threadsafe(pending, loop).result(timeout=5)
            listener.on_action_result({"type": "action_result"})
            listener.on_game_over()

            assert ws.send_json.await_count == 1
        finally:
            loop.call_soon_threadsafe(loop.stop)
            runner.join(timeout=5)
            loop.close()
