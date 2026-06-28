"""Tests for click-to-move: BFS pathfinding and handle_move_to handler."""

from __future__ import annotations

import itertools
from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.combat import BattleMap, Position, Wall
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.movement import compute_reachable, find_path, step_cost
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

    def test_find_path_uses_cost_aware_routing(self) -> None:
        """find_path returns the cost-optimal path, not the step-count-optimal path.

        This is the root cause fix: old BFS minimized steps (preferring diagonals)
        which could produce paths that cost more feet than necessary.
        """
        bm = BattleMap(width=60, height=60)
        start = Position(15, 15)
        goal = Position(45, 15)  # 6 squares east = 30ft straight
        path = find_path(start, goal, bm, "mover")
        assert path[-1] == goal
        # Walk the path — cost should be exactly 30ft (pure cardinal)
        # Old BFS might pick diagonal shortcuts that cost more due to alternating rule
        cost = 0
        diag_count = 0
        for a, b in itertools.pairwise(path):
            step, diag_count = step_cost(a, b, diag_count)
            cost += step
        assert cost == 30

    def test_find_path_matches_compute_reachable(self) -> None:
        """find_path returns same path as compute_reachable for the same target."""
        bm = BattleMap(width=60, height=60, walls=[Wall(20, 0, 20, 20)])
        start = Position(15, 10)
        goal = Position(25, 10)
        path_direct = find_path(start, goal, bm, "mover")
        reachable = compute_reachable(start, 999, bm, "mover")
        path_reachable = reachable.get(goal, [])
        # Both should find the same optimal path
        assert path_direct == path_reachable


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

    def test_move_to_edge_of_range_reaches_target(self) -> None:
        """Edge-of-range bug fix: clicking a cell at exact budget limit should reach it.

        With 30ft budget, a cell at exactly 30ft via the optimal path must be reached.
        The old BFS could pick a path with more diagonals (fewer steps but higher cost),
        causing the walk to stop short.
        """
        from dnd_simulator.rules.handlers.movement import handle_move_to

        bm = BattleMap(width=60, height=60)
        bm.set_position("player", Position(15, 15))
        # Target: 4 diagonal steps = 5+10+5+10 = 30ft exactly
        ctx = self._make_ctx(bm, movement_remaining=30)
        actor = self._make_creature()
        action = Action(name=ActionType.MOVE_TO, params={"x": 35, "y": 35})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_move_to(actor, action, emit_fn, ctx, world)

        assert result.success
        assert bm.get_position("player") == Position(35, 35)
        assert ctx.turn_budget is not None
        assert ctx.turn_budget.movement_remaining == 0

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
