"""Tests for ActionDispatcher — validate → route → execute → budget."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import ActionResult, EmitFn, Event, EventType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.rules.action_handlers import (
    handle_attack,
    handle_dash,
    handle_dodge,
    handle_flee,
    handle_idle,
    handle_move,
    handle_say,
    handle_wait,
)
from dnd_simulator.rules.validation import ActionContext
from dnd_simulator.service.action_dispatcher import create_dispatcher


def _creature(*, alive: bool = True, active: bool = True, speed: int = 30) -> Creature:
    c = Creature(id="test", name="Test", location_id="loc", speed=speed)
    if not alive:
        c.current_hp = 0
    if not active:
        c.active = False
    return c


def _noop_emit(event: Event) -> ActionResult:
    return ActionResult()


def _capture_emit() -> tuple[list[Event], EmitFn]:
    emitted: list[Event] = []

    def emit(event: Event) -> ActionResult:
        emitted.append(event)
        return ActionResult()

    return emitted, emit


# Stub world for handler/dispatcher tests — handlers don't use it yet.
# MagicMock so that accidental attribute access fails with a clear trace, not AttributeError on None.
_WORLD = cast(World, MagicMock(spec=World))

_COMBAT = ActionContext(is_combat=True, current_turn_entity_id="test")
_PEACEFUL = ActionContext(is_combat=False, current_turn_entity_id="test")


def _combat_ctx(budget: TurnBudget) -> ActionContext:
    return ActionContext(is_combat=True, current_turn_entity_id="test", turn_budget=budget)


# ---------------------------------------------------------------------------
# dispatch: validate → route → execute
# ---------------------------------------------------------------------------


class TestDispatchBasic:
    def test_idle_success(self) -> None:
        d = create_dispatcher(_WORLD)
        result = d.dispatch(_creature(), Action(name=ActionType.IDLE), _PEACEFUL, _noop_emit)
        assert result.success

    def test_say_success(self) -> None:
        d = create_dispatcher(_WORLD)
        action = Action(name=ActionType.SAY, params={"text": "hello"})
        result = d.dispatch(_creature(), action, _PEACEFUL, _noop_emit)
        assert result.success

    def test_attack_success(self) -> None:
        d = create_dispatcher(_WORLD)
        action = Action(name=ActionType.ATTACK, params={"target_id": "goblin_1"})
        result = d.dispatch(_creature(), action, _COMBAT, _noop_emit)
        assert result.success

    def test_dead_actor_rejected(self) -> None:
        d = create_dispatcher(_WORLD)
        result = d.dispatch(_creature(alive=False), Action(name=ActionType.IDLE), _PEACEFUL, _noop_emit)
        assert not result.success
        assert result.error

    def test_dormant_actor_rejected(self) -> None:
        d = create_dispatcher(_WORLD)
        result = d.dispatch(_creature(active=False), Action(name=ActionType.IDLE), _PEACEFUL, _noop_emit)
        assert not result.success

    def test_unknown_action_raises_key_error(self) -> None:
        d = create_dispatcher(_WORLD)
        with pytest.raises(KeyError):
            d.dispatch(_creature(), Action(name="fireball"), _PEACEFUL, _noop_emit)

    def test_combat_only_action_in_peaceful_rejected(self) -> None:
        d = create_dispatcher(_WORLD)
        result = d.dispatch(_creature(), Action(name=ActionType.DODGE), _PEACEFUL, _noop_emit)
        assert not result.success


# ---------------------------------------------------------------------------
# dispatch: budget enforcement
# ---------------------------------------------------------------------------


class TestDispatchBudget:
    def test_no_budget_no_problem(self) -> None:
        """Peaceful turns have no budget — actions always execute."""
        d = create_dispatcher(_WORLD)
        ctx = ActionContext(is_combat=False, current_turn_entity_id="test")
        result = d.dispatch(_creature(), Action(name=ActionType.IDLE), ctx, _noop_emit)
        assert result.success

    def test_budget_not_consumed_for_free_action(self) -> None:
        """Idle and say cost nothing — budget unchanged after dispatch."""
        budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30)
        ctx = _combat_ctx(budget)
        d = create_dispatcher(_WORLD)
        result = d.dispatch(_creature(), Action(name=ActionType.IDLE), ctx, _noop_emit)
        assert result.success
        assert budget.actions == 1  # unchanged — idle is free

    def test_budget_insufficient_rejected(self) -> None:
        """If budget can't afford the action, dispatch returns error without executing."""
        budget = TurnBudget(actions=0, bonus_actions=0, movement_remaining=0)
        ctx = _combat_ctx(budget)
        d = create_dispatcher(_WORLD)
        result = d.dispatch(_creature(), Action(name=ActionType.ATTACK), ctx, _noop_emit)
        assert not result.success
        assert "budget" in result.error.lower()

    def test_budget_consumed_on_success(self) -> None:
        """Successful action consumes budget."""
        budget = TurnBudget(actions=2, bonus_actions=0, movement_remaining=30)
        ctx = _combat_ctx(budget)
        d = create_dispatcher(_WORLD)
        result = d.dispatch(_creature(), Action(name=ActionType.ATTACK), ctx, _noop_emit)
        assert result.success
        assert budget.actions == 1  # consumed 1

    def test_budget_not_consumed_on_failure(self) -> None:
        """Failed handler doesn't consume budget."""
        budget = TurnBudget(actions=2, bonus_actions=0, movement_remaining=30)
        ctx = _combat_ctx(budget)

        def failing_emit(event: Event) -> ActionResult:
            return ActionResult(success=False, error="invalid target")

        d = create_dispatcher(_WORLD)
        result = d.dispatch(_creature(), Action(name=ActionType.ATTACK), ctx, failing_emit)
        assert not result.success
        assert budget.actions == 2  # unchanged

    def test_move_consumes_movement(self) -> None:
        budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30)
        ctx = _combat_ctx(budget)
        d = create_dispatcher(_WORLD)
        action = Action(name=ActionType.MOVE, params={"direction": "N", "ft": 10})
        result = d.dispatch(_creature(), action, ctx, _noop_emit)
        assert result.success
        assert budget.movement_remaining == 20

    def test_move_insufficient_movement_rejected(self) -> None:
        budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=5)
        ctx = _combat_ctx(budget)
        d = create_dispatcher(_WORLD)
        action = Action(name=ActionType.MOVE, params={"direction": "N", "ft": 10})
        result = d.dispatch(_creature(), action, ctx, _noop_emit)
        assert not result.success

    def test_dash_consumes_action_adds_movement(self) -> None:
        """Dash costs 1 action and adds effective speed to movement pool."""
        budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30)
        ctx = _combat_ctx(budget)
        d = create_dispatcher(_WORLD)
        creature = _creature(speed=30)
        result = d.dispatch(creature, Action(name=ActionType.DASH), ctx, _noop_emit)
        assert result.success
        assert budget.actions == 0  # consumed 1 action
        assert budget.movement_remaining == 60  # 30 original + 30 from dash

    def test_dash_no_actions_rejected(self) -> None:
        budget = TurnBudget(actions=0, bonus_actions=0, movement_remaining=30)
        ctx = _combat_ctx(budget)
        d = create_dispatcher(_WORLD)
        result = d.dispatch(_creature(), Action(name=ActionType.DASH), ctx, _noop_emit)
        assert not result.success


# ---------------------------------------------------------------------------
# handlers: idle and say
# ---------------------------------------------------------------------------


class TestHandleIdle:
    def test_idle_returns_success(self) -> None:
        result = handle_idle(_creature(), Action(name=ActionType.IDLE), _noop_emit, _PEACEFUL, _WORLD)
        assert result.success

    def test_idle_inspect_emits_custom_event(self) -> None:
        emitted, emit = _capture_emit()
        action = Action(name=ActionType.IDLE, params={"inspect_target": "goblin_1"})
        handle_idle(_creature(), action, emit, _PEACEFUL, _WORLD)
        assert len(emitted) == 1
        assert emitted[0].event_type == EventType.CUSTOM
        assert emitted[0].data["inspect_target"] == "goblin_1"

    def test_idle_no_inspect_no_event(self) -> None:
        emitted, emit = _capture_emit()
        handle_idle(_creature(), Action(name=ActionType.IDLE), emit, _PEACEFUL, _WORLD)
        assert len(emitted) == 0


class TestHandleSay:
    def test_say_emits_event(self) -> None:
        emitted, emit = _capture_emit()
        action = Action(name=ActionType.SAY, params={"text": "Hello!"})
        result = handle_say(_creature(), action, emit, _PEACEFUL, _WORLD)
        assert result.success
        assert len(emitted) == 1
        assert emitted[0].event_type == EventType.ENTITY_SAY
        assert emitted[0].data["text"] == "Hello!"


# ---------------------------------------------------------------------------
# handlers: combat actions
# ---------------------------------------------------------------------------


class TestHandleAttack:
    def test_attack_emits_event(self) -> None:
        emitted, emit = _capture_emit()
        action = Action(name=ActionType.ATTACK, params={"target_id": "goblin_1"})
        result = handle_attack(_creature(), action, emit, _COMBAT, _WORLD)
        assert result.success
        assert len(emitted) == 1
        assert emitted[0].event_type == EventType.ENTITY_ATTACK
        assert emitted[0].data["attacker_id"] == "test"
        assert emitted[0].data["target_id"] == "goblin_1"


class TestHandleDodge:
    def test_dodge_emits_event(self) -> None:
        emitted, emit = _capture_emit()
        result = handle_dodge(_creature(), Action(name=ActionType.DODGE), emit, _COMBAT, _WORLD)
        assert result.success
        assert len(emitted) == 1
        assert emitted[0].event_type == EventType.ENTITY_DODGE


class TestHandleFlee:
    def test_flee_emits_event(self) -> None:
        emitted, emit = _capture_emit()
        result = handle_flee(_creature(), Action(name=ActionType.FLEE), emit, _COMBAT, _WORLD)
        assert result.success
        assert len(emitted) == 1
        assert emitted[0].event_type == EventType.ENTITY_FLEE


class TestHandleMove:
    def test_move_emits_event(self) -> None:
        emitted, emit = _capture_emit()
        action = Action(name=ActionType.MOVE, params={"direction": "N", "ft": 10})
        result = handle_move(_creature(), action, emit, _COMBAT, _WORLD)
        assert result.success
        assert len(emitted) == 1
        assert emitted[0].event_type == EventType.ENTITY_MOVE
        assert emitted[0].data["direction"] == "N"
        assert emitted[0].data["ft"] == 10


class TestHandleWait:
    def test_wait_sets_wake_at_and_dormant(self) -> None:
        world = MagicMock()
        world.time.to_total_seconds.return_value = 10000
        creature = _creature()
        action = Action(name=ActionType.WAIT, params={"hours": 2})
        result = handle_wait(creature, action, _noop_emit, _PEACEFUL, world)
        assert result.success
        assert creature.wake_at_seconds == 10000 + 2 * 3600
        assert creature.active is False

    def test_wait_default_1_hour(self) -> None:
        world = MagicMock()
        world.time.to_total_seconds.return_value = 5000
        creature = _creature()
        action = Action(name=ActionType.WAIT)
        result = handle_wait(creature, action, _noop_emit, _PEACEFUL, world)
        assert result.success
        assert creature.wake_at_seconds == 5000 + 3600

    def test_wait_emits_no_event(self) -> None:
        world = MagicMock()
        world.time.to_total_seconds.return_value = 0
        emitted, emit = _capture_emit()
        action = Action(name=ActionType.WAIT, params={"hours": 1})
        handle_wait(_creature(), action, emit, _PEACEFUL, world)
        assert len(emitted) == 0

    def test_wait_travel(self) -> None:
        world = MagicMock()
        world.location_graph.travel_seconds.return_value = 600
        creature = _creature()
        creature.location_id = "loc_a"
        action = Action(name=ActionType.WAIT, params={"travel_to": "loc_b"})
        result = handle_wait(creature, action, _noop_emit, _PEACEFUL, world)
        assert result.success
        assert creature.location_id == "loc_b"
        world.advance_time.assert_called_once()


class TestHandleDash:
    def test_dash_adds_movement(self) -> None:
        budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30)
        ctx = _combat_ctx(budget)
        creature = _creature(speed=25)
        result = handle_dash(creature, Action(name=ActionType.DASH), _noop_emit, ctx, _WORLD)
        assert result.success
        assert budget.movement_remaining == 55  # 30 + 25

    def test_dash_without_budget_fails(self) -> None:
        result = handle_dash(_creature(), Action(name=ActionType.DASH), _noop_emit, _PEACEFUL, _WORLD)
        assert not result.success

    def test_dash_emits_no_event(self) -> None:
        budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30)
        ctx = _combat_ctx(budget)
        emitted, emit = _capture_emit()
        handle_dash(_creature(), Action(name=ActionType.DASH), emit, ctx, _WORLD)
        assert len(emitted) == 0


# ---------------------------------------------------------------------------
# has_handler / create_dispatcher
# ---------------------------------------------------------------------------


class TestHasHandler:
    def test_all_standard_actions_registered(self) -> None:
        d = create_dispatcher(_WORLD)
        for name in (
            ActionType.IDLE,
            ActionType.SAY,
            ActionType.ATTACK,
            ActionType.DODGE,
            ActionType.FLEE,
            ActionType.MOVE,
            ActionType.DASH,
            ActionType.WAIT,
        ):
            assert d.has_handler(name), f"{name} not registered"

    def test_unknown_not_registered(self) -> None:
        d = create_dispatcher(_WORLD)
        assert not d.has_handler("fireball")

    def test_world_accessible(self) -> None:
        d = create_dispatcher(_WORLD)
        assert d.world is _WORLD


# ---------------------------------------------------------------------------
# get_available_actions
# ---------------------------------------------------------------------------


class TestGetAvailableActions:
    def test_peaceful_excludes_combat_only(self) -> None:
        """Peaceful context should not include dodge, flee, dash."""
        d = create_dispatcher(_WORLD)
        available = d.get_available_actions(_creature(), _PEACEFUL)
        assert ActionType.SAY in available
        assert ActionType.IDLE in available
        assert ActionType.ATTACK in available
        assert ActionType.WAIT in available
        assert ActionType.DODGE not in available
        assert ActionType.FLEE not in available
        assert ActionType.DASH not in available

    def test_combat_excludes_say(self) -> None:
        """Combat context should not include say."""
        budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30)
        ctx = _combat_ctx(budget)
        d = create_dispatcher(_WORLD)
        available = d.get_available_actions(_creature(), ctx)
        assert ActionType.SAY not in available
        assert ActionType.ATTACK in available
        assert ActionType.DODGE in available
        assert ActionType.MOVE in available

    def test_no_actions_budget_excludes_standard(self) -> None:
        """With 0 actions, standard-cost actions (attack, dodge, dash, flee) unavailable."""
        budget = TurnBudget(actions=0, bonus_actions=0, movement_remaining=30)
        ctx = _combat_ctx(budget)
        d = create_dispatcher(_WORLD)
        available = d.get_available_actions(_creature(), ctx)
        assert ActionType.ATTACK not in available
        assert ActionType.DODGE not in available
        assert ActionType.DASH not in available
        # Free actions still available
        assert ActionType.IDLE in available
        # Movement still available
        assert ActionType.MOVE in available

    def test_no_movement_excludes_move(self) -> None:
        """With 0 movement, move is unavailable."""
        budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=0)
        ctx = _combat_ctx(budget)
        d = create_dispatcher(_WORLD)
        available = d.get_available_actions(_creature(), ctx)
        assert ActionType.MOVE not in available
        assert ActionType.ATTACK in available

    def test_dead_creature_gets_nothing(self) -> None:
        d = create_dispatcher(_WORLD)
        available = d.get_available_actions(_creature(alive=False), _PEACEFUL)
        assert available == []

    def test_dormant_creature_gets_nothing(self) -> None:
        d = create_dispatcher(_WORLD)
        available = d.get_available_actions(_creature(active=False), _PEACEFUL)
        assert available == []
