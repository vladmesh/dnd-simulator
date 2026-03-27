"""Tests for click-to-move: BFS pathfinding and handle_move_to handler."""

from __future__ import annotations

import itertools
from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.combat import BattleMap, Position, Wall
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.movement import find_path, walk_path
from dnd_simulator.rules.validation import ActionContext

# ---------------------------------------------------------------------------
# find_path — BFS pathfinding on the battle map grid
# ---------------------------------------------------------------------------


class TestFindPath:
    def test_path_on_empty_map(self) -> None:
        bm = BattleMap(width=30, height=30)
        path = find_path(Position(0, 0), Position(15, 10), bm, "mover")
        assert len(path) > 0
        assert path[0] == Position(0, 0)
        assert path[-1] == Position(15, 10)
        # Each step is adjacent (5ft)
        for a, b in itertools.pairwise(path):
            assert abs(a.x - b.x) <= 5 and abs(a.y - b.y) <= 5

    def test_path_around_wall(self) -> None:
        # Wall blocks direct east movement at x=10 from y=0 to y=15
        bm = BattleMap(width=30, height=30, walls=[Wall(10, 0, 10, 15)])
        path = find_path(Position(5, 5), Position(15, 5), bm, "mover")
        assert len(path) > 0
        assert path[-1] == Position(15, 5)
        # Path goes around the wall — no step crosses x=10 between y=0..15
        for a, b in itertools.pairwise(path):
            if not bm.is_step_blocked(a, b):
                continue
            pytest.fail(f"Path crosses a wall: {a} -> {b}")

    def test_path_around_occupied_cell(self) -> None:
        bm = BattleMap(width=30, height=30)
        bm.set_position("blocker", Position(10, 5))
        bm.set_position("mover", Position(5, 5))
        path = find_path(Position(5, 5), Position(15, 5), bm, "mover")
        assert len(path) > 0
        assert path[-1] == Position(15, 5)
        # Path does not pass through blocker position
        assert Position(10, 5) not in path[1:]  # start may coincide, but intermediates don't

    def test_unreachable_returns_empty(self) -> None:
        # Surround the target with walls
        bm = BattleMap(
            width=30,
            height=30,
            walls=[
                Wall(10, 5, 10, 15),  # left
                Wall(20, 5, 20, 15),  # right
                Wall(10, 15, 20, 15),  # top
                Wall(10, 5, 20, 5),  # bottom
            ],
        )
        path = find_path(Position(0, 0), Position(15, 10), bm, "mover")
        assert path == []

    def test_same_position_returns_single_element(self) -> None:
        bm = BattleMap(width=30, height=30)
        path = find_path(Position(10, 10), Position(10, 10), bm, "mover")
        assert path == [Position(10, 10)]


# ---------------------------------------------------------------------------
# walk_path — walk a path spending movement budget
# ---------------------------------------------------------------------------


class TestWalkPath:
    def test_walk_full_path_within_budget(self) -> None:
        # Straight line 3 squares = 15ft, budget = 30ft
        path = [Position(0, 0), Position(5, 0), Position(10, 0), Position(15, 0)]
        final_pos, feet_spent = walk_path(path, 30)
        assert final_pos == Position(15, 0)
        assert feet_spent == 15

    def test_walk_stops_at_budget_limit(self) -> None:
        # 8 squares straight = 40ft, budget = 30ft → stop after 6 squares
        path = [Position(i * 5, 0) for i in range(9)]  # 0 to 40ft
        final_pos, feet_spent = walk_path(path, 30)
        assert final_pos == Position(30, 0)
        assert feet_spent == 30

    def test_diagonal_alternating_cost(self) -> None:
        # Diagonal path: first diag = 5ft, second = 10ft, third = 5ft
        path = [Position(0, 0), Position(5, 5), Position(10, 10), Position(15, 15)]
        # Cost: 5 + 10 + 5 = 20ft
        final_pos, feet_spent = walk_path(path, 30)
        assert final_pos == Position(15, 15)
        assert feet_spent == 20

    def test_budget_35_on_diagonal_stops_at_30(self) -> None:
        # 7 diagonal steps, budget = 30ft
        # Cost: 5 + 10 + 5 + 10 + 5 = 35ft for 5 steps, but 30ft budget
        # After 4 diags: 5+10+5+10 = 30ft
        path = [Position(i * 5, i * 5) for i in range(8)]
        final_pos, feet_spent = walk_path(path, 30)
        assert final_pos == Position(20, 20)
        assert feet_spent == 30

    def test_empty_path(self) -> None:
        _final_pos, feet_spent = walk_path([], 30)
        assert feet_spent == 0

    def test_single_position_path(self) -> None:
        final_pos, feet_spent = walk_path([Position(10, 10)], 30)
        assert final_pos == Position(10, 10)
        assert feet_spent == 0


# ---------------------------------------------------------------------------
# handle_move_to — action handler integration
# ---------------------------------------------------------------------------


class TestHandleMoveTo:
    """Integration tests for the handle_move_to handler."""

    def _make_ctx(self, battle_map: BattleMap, movement_remaining: int = 30) -> ActionContext:
        from dnd_simulator.core.combat import CombatState

        combat_state = CombatState(location_id="loc", battle_map=battle_map)
        budget = TurnBudget(movement_remaining=movement_remaining)
        return ActionContext(is_combat=True, combat_state=combat_state, turn_budget=budget)

    def _make_creature(self, creature_id: str = "player") -> MagicMock:
        creature = MagicMock()
        creature.id = creature_id
        creature.location_id = "loc"
        return creature

    def test_move_to_valid_target(self) -> None:
        from dnd_simulator.rules.handlers.movement import handle_move_to

        bm = BattleMap(width=30, height=30)
        bm.set_position("player", Position(0, 0))
        ctx = self._make_ctx(bm, movement_remaining=30)
        actor = self._make_creature()
        action = Action(name=ActionType.MOVE_TO, params={"x": 15, "y": 10})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_move_to(actor, action, emit_fn, ctx, world)

        assert result.success
        assert bm.get_position("player") == Position(15, 10)
        assert ctx.turn_budget is not None
        assert ctx.turn_budget.movement_remaining < 30

    def test_move_to_unreachable_target(self) -> None:
        from dnd_simulator.rules.handlers.movement import handle_move_to

        # Surround target with walls
        bm = BattleMap(
            width=30,
            height=30,
            walls=[
                Wall(10, 5, 10, 15),
                Wall(20, 5, 20, 15),
                Wall(10, 15, 20, 15),
                Wall(10, 5, 20, 5),
            ],
        )
        bm.set_position("player", Position(0, 0))
        ctx = self._make_ctx(bm)
        actor = self._make_creature()
        action = Action(name=ActionType.MOVE_TO, params={"x": 15, "y": 10})

        result = handle_move_to(actor, action, MagicMock(), ctx, MagicMock())

        assert not result.success

    def test_move_to_occupied_cell(self) -> None:
        from dnd_simulator.rules.handlers.movement import handle_move_to

        bm = BattleMap(width=30, height=30)
        bm.set_position("player", Position(0, 0))
        bm.set_position("enemy", Position(10, 10))
        ctx = self._make_ctx(bm)
        actor = self._make_creature()
        action = Action(name=ActionType.MOVE_TO, params={"x": 10, "y": 10})

        result = handle_move_to(actor, action, MagicMock(), ctx, MagicMock())

        assert not result.success

    def test_existing_move_direction_still_works(self) -> None:
        """Regression: the original direction-based move action still works."""
        from dnd_simulator.rules.handlers.movement import handle_move

        bm = BattleMap(width=30, height=30)
        bm.set_position("player", Position(0, 0))

        from dnd_simulator.core.combat import CombatState

        combat_state = CombatState(location_id="loc", battle_map=bm)
        ctx = ActionContext(
            is_combat=True,
            combat_state=combat_state,
            turn_budget=TurnBudget(movement_remaining=30),
        )
        actor = self._make_creature()
        action = Action(name=ActionType.MOVE, params={"direction": "north", "ft": 5})
        emit_fn = MagicMock(return_value=ActionResult())

        result = handle_move(actor, action, emit_fn, ctx, MagicMock())

        assert result.success
        # emit_fn was called with an ENTITY_MOVE event
        emit_fn.assert_called_once()
