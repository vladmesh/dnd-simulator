"""Tests for D&D 5e movement rules — diagonal distance and grid movement, including walls."""

from __future__ import annotations

from dnd_simulator.core.combat import BattleMap, Position, Wall
from dnd_simulator.rules.movement import (
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


class TestMoveWithWalls:
    """Movement stops at walls instead of passing through."""

    def test_move_direction_stops_at_horizontal_wall(self) -> None:
        bm = BattleMap(width=100, height=100, walls=[Wall(0, 40, 60, 40)])
        origin = Position(10, 20)
        result = move_direction(origin, "north", speed=30, battle_map=bm)
        # Should stop at y=35 (one square before wall at y=40)
        assert result.y <= 35
