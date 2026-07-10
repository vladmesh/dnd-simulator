from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import ActionResult, TimeDelta
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger, TriggerType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.round import Round
from dnd_simulator.rules.rule_brain import RuleBrain
from dnd_simulator.rules.validation import ActionContext
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

_FIGHTER_DATA = {
    "name": "Thrain",
    "race": "dwarf",
    "class": "fighter",
    "alignment": "lawful_good",
    "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
    "fighting_style": "defense",
}


def _service(tmp_path: Path) -> GameService:
    return GameService(store=JsonFileStore(tmp_path / "saves"))


def test_save_waits_for_complete_world_mutation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.start_game("sword_vale")
    mutation_started = threading.Event()
    release_mutation = threading.Event()
    save_done = threading.Event()
    saved: list[Any] = []

    def mutate() -> None:
        with session.mutate_world():
            session.world.advance_time(TimeDelta(seconds=6))
            mutation_started.set()
            assert release_mutation.wait(timeout=2)

    def snapshot() -> None:
        saved.append(service._build_save_game(session.session_id))
        save_done.set()

    mutation_thread = threading.Thread(target=mutate)
    mutation_thread.start()
    assert mutation_started.wait(timeout=2)
    save_thread = threading.Thread(target=snapshot)
    save_thread.start()

    assert not save_done.wait(timeout=0.05)
    release_mutation.set()
    mutation_thread.join(timeout=2)
    save_thread.join(timeout=2)

    assert save_done.is_set()
    assert saved[0].world.time == session.world.time.to_dict()


def test_snapshot_is_available_while_player_brain_waits(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.start_game("sword_vale")
    service.create_player(session.session_id, _FIGHTER_DATA)
    player = session.get_player()
    assert player is not None
    session.start_round(player)

    snapshot_acquired = threading.Event()

    def snapshot() -> None:
        with session.read_world():
            snapshot_acquired.set()

    thread = threading.Thread(target=snapshot)
    thread.start()
    try:
        assert snapshot_acquired.wait(timeout=2)
    finally:
        session.stop_round()
        thread.join(timeout=2)


def test_action_and_nested_reaction_use_one_reentrant_gate() -> None:
    lock = threading.RLock()
    depth = 0
    observed_depths: list[int] = []

    @contextmanager
    def mutation_scope() -> Any:
        nonlocal depth
        with lock:
            depth += 1
            try:
                yield
            finally:
                depth -= 1

    reactor = Creature(id="guard", name="Guard", location_id="arena")
    reactor.brain = RuleBrain()
    reactor.turn_budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30, reaction=1)
    host = MagicMock()
    host.get_entity.return_value = reactor
    host.get_combat.return_value = None
    dispatcher = MagicMock()
    game_round = Round(MagicMock(), host, dispatcher=dispatcher, mutation_scope=mutation_scope)
    nested = False

    def dispatch(*args: object) -> ActionResult:
        nonlocal nested
        observed_depths.append(depth)
        if not nested:
            nested = True
            game_round.check_reactions(
                ReactionTrigger(trigger_type=TriggerType.LEAVING_REACH, source_creature_id="mover"),
                [ReactionOption(action_type=ActionType.OPPORTUNITY_ATTACK, description="OA")],
                [reactor],
            )
        return ActionResult()

    dispatcher.dispatch.side_effect = dispatch
    game_round._execute_action(
        reactor,
        Action(name=ActionType.DODGE),
        ActionContext(is_combat=True),
        lambda event: ActionResult(),
    )

    assert observed_depths == [1, 2]


def test_stop_round_and_concurrent_snapshot_finish_without_deadlock(tmp_path: Path) -> None:
    service = _service(tmp_path)
    session = service.start_game("sword_vale")
    service.create_player(session.session_id, _FIGHTER_DATA)
    player = session.get_player()
    assert player is not None
    session.start_round(player)

    snapshot_thread = threading.Thread(target=lambda: service._build_save_game(session.session_id))
    stop_thread = threading.Thread(target=session.stop_round)
    snapshot_thread.start()
    stop_thread.start()
    snapshot_thread.join(timeout=2)
    stop_thread.join(timeout=2)

    assert not snapshot_thread.is_alive()
    assert not stop_thread.is_alive()
