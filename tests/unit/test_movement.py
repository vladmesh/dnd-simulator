"""Tests for D&D 5e movement rules — diagonal distance and grid movement, including walls."""

from __future__ import annotations

import itertools

from dnd_simulator.core.combat import BattleMap, Position, Wall
from dnd_simulator.rules.movement import (
    compute_reachable,
    direction_label,
    grid_distance,
    move_direction,
)


class TestGridDistance:
    """D&D 5e DMG diagonal rule: first diag = 5, second = 10, alternating."""

    def test_same_position(self) -> None:
        assert grid_distance(Position(0, 0), Position(0, 0)) == 0

    def test_straight_horizontal(self) -> None:
        assert grid_distance(Position(0, 0), Position(30, 0)) == 30

    def test_straight_vertical(self) -> None:
        assert grid_distance(Position(0, 0), Position(0, 25)) == 25

    def test_one_diagonal(self) -> None:
        # 1 square diagonal = 5 ft
        assert grid_distance(Position(0, 0), Position(5, 5)) == 5

    def test_two_diagonals(self) -> None:
        # 2 diagonal squares: first = 5, second = 10 → total = 15
        assert grid_distance(Position(0, 0), Position(10, 10)) == 15

    def test_three_diagonals(self) -> None:
        # 3 diags: 5 + 10 + 5 = 20
        assert grid_distance(Position(0, 0), Position(15, 15)) == 20

    def test_four_diagonals(self) -> None:
        # 4 diags: 5 + 10 + 5 + 10 = 30
        assert grid_distance(Position(0, 0), Position(20, 20)) == 30

    def test_mixed_diagonal_and_straight(self) -> None:
        # dx=3 squares, dy=1 square → 1 diag + 2 straight = 5 + 10 = 15
        assert grid_distance(Position(0, 0), Position(15, 5)) == 15

    def test_symmetric(self) -> None:
        a, b = Position(10, 20), Position(30, 5)
        assert grid_distance(a, b) == grid_distance(b, a)


class TestDirectionLabel:
    def test_north(self) -> None:
        assert direction_label(0, 1) == "to the north"

    def test_south(self) -> None:
        assert direction_label(0, -1) == "to the south"

    def test_east(self) -> None:
        assert direction_label(1, 0) == "to the east"

    def test_west(self) -> None:
        assert direction_label(-1, 0) == "to the west"

    def test_northeast(self) -> None:
        assert direction_label(1, 1) == "to the northeast"

    def test_southwest(self) -> None:
        assert direction_label(-1, -1) == "to the southwest"

    def test_same_position(self) -> None:
        assert direction_label(0, 0) == "here"


class TestMoveDirection:
    def test_move_north(self) -> None:
        bm = BattleMap(width=100, height=100)
        origin = Position(50, 0)
        result = move_direction(origin, "north", speed=30, battle_map=bm)
        assert result == Position(50, 30)

    def test_move_southwest(self) -> None:
        bm = BattleMap(width=100, height=100)
        origin = Position(50, 50)
        result = move_direction(origin, "southwest", speed=30, battle_map=bm)
        assert result.x < origin.x
        assert result.y < origin.y

    def test_invalid_direction_stays(self) -> None:
        bm = BattleMap(width=100, height=100)
        origin = Position(50, 50)
        result = move_direction(origin, "upward", speed=30, battle_map=bm)
        assert result == origin

    def test_clamp_to_map_edge(self) -> None:
        bm = BattleMap(width=40, height=40)
        origin = Position(10, 10)
        result = move_direction(origin, "south", speed=60, battle_map=bm)
        assert result.y >= 0


class TestComputeReachable:
    """compute_reachable: Dijkstra BFS with D&D 5e diagonal costs."""

    def test_open_field_cardinal_at_budget(self) -> None:
        """Cells exactly 30ft away in cardinal direction are reachable."""
        bm = BattleMap(width=60, height=60)
        reachable = compute_reachable(Position(15, 15), 30, bm, "mover")
        # 6 squares east = 30ft
        assert Position(45, 15) in reachable
        # 7 squares east = 35ft → not reachable
        assert Position(50, 15) not in reachable

    def test_open_field_diagonal_cost(self) -> None:
        """5 diagonal steps cost 5+10+5+10+5=35ft — not reachable at 30ft budget."""
        bm = BattleMap(width=60, height=60)
        reachable = compute_reachable(Position(15, 15), 30, bm, "mover")
        # 5 diags = 35ft → unreachable
        assert Position(40, 40) not in reachable
        # 4 diags = 30ft → reachable
        assert Position(35, 35) in reachable

    def test_wall_blocks_direct_path(self) -> None:
        """Wall blocks direct east; detour around wall is reachable if within budget."""
        # Vertical wall at x=20 from y=0 to y=20 blocks east movement
        bm = BattleMap(width=60, height=60, walls=[Wall(20, 0, 20, 20)])
        reachable = compute_reachable(Position(15, 10), 30, bm, "mover")
        # Directly east at x=25 requires detour around wall
        # The cell should still be reachable via going north around wall
        assert Position(25, 10) in reachable
        # Path should go around the wall, not through it
        path = reachable[Position(25, 10)]
        for a, b in itertools.pairwise(path):
            assert not bm.is_step_blocked(a, b), f"Path crosses wall: {a} -> {b}"

    def test_wall_makes_cell_unreachable_if_detour_too_long(self) -> None:
        """Wall forces long detour that exceeds budget."""
        # Long wall blocks east, only opening at top — detour is very long
        bm = BattleMap(width=60, height=60, walls=[Wall(20, 0, 20, 55)])
        reachable = compute_reachable(Position(15, 10), 30, bm, "mover")
        # Cell east of wall at same y — detour must go all the way to y=55+
        # That's way more than 30ft
        assert Position(25, 10) not in reachable

    def test_occupied_cell_not_reachable(self) -> None:
        """Cells occupied by other entities are not in reachable set."""
        bm = BattleMap(width=60, height=60)
        bm.set_position("enemy", Position(20, 15))
        bm.set_position("mover", Position(15, 15))
        reachable = compute_reachable(Position(15, 15), 30, bm, "mover")
        assert Position(20, 15) not in reachable

    def test_cells_behind_occupied_are_reachable_via_detour(self) -> None:
        """Cells beyond an occupied cell are reachable via alternate route."""
        bm = BattleMap(width=60, height=60)
        bm.set_position("enemy", Position(20, 15))
        bm.set_position("mover", Position(15, 15))
        reachable = compute_reachable(Position(15, 15), 30, bm, "mover")
        # Cell beyond enemy is reachable via diagonal detour
        assert Position(25, 15) in reachable

    def test_path_cost_matches_budget(self) -> None:
        """Path to edge-of-range cell costs exactly the grid_distance."""
        bm = BattleMap(width=60, height=60)
        start = Position(15, 15)
        reachable = compute_reachable(start, 30, bm, "mover")
        # 4 diags = 5+10+5+10 = 30ft exactly
        target = Position(35, 35)
        assert target in reachable
        # Walk the path and verify cost
        from dnd_simulator.rules.movement import step_cost

        path = reachable[target]
        cost = 0
        diag_count = 0
        for a, b in itertools.pairwise(path):
            step, diag_count = step_cost(a, b, diag_count)
            cost += step
        assert cost == 30

    def test_start_position_in_reachable(self) -> None:
        """Start position is always in the reachable set (cost 0)."""
        bm = BattleMap(width=60, height=60)
        start = Position(15, 15)
        reachable = compute_reachable(start, 30, bm, "mover")
        assert start in reachable
        assert reachable[start] == [start]


class TestMoveWithWalls:
    """Movement stops at walls instead of passing through."""

    def test_move_direction_stops_at_horizontal_wall(self) -> None:
        bm = BattleMap(width=100, height=100, walls=[Wall(0, 40, 60, 40)])
        origin = Position(10, 20)
        result = move_direction(origin, "north", speed=30, battle_map=bm)
        # Should stop at y=35 (one square before wall at y=40)
        assert result.y <= 35
