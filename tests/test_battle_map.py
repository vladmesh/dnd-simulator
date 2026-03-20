"""Tests for BattleMap — placement, bounds clamping, random scatter, walls."""

from __future__ import annotations

import random

from dnd_simulator.core.combat import BattleMap, Position, Wall


class TestBattleMap:
    def test_set_and_get_position(self) -> None:
        bm = BattleMap(width=60, height=60)
        bm.set_position("a", Position(10, 20))
        assert bm.get_position("a") == Position(10, 20)

    def test_set_position_clamps_to_bounds(self) -> None:
        bm = BattleMap(width=40, height=30)
        bm.set_position("a", Position(100, -10))
        pos = bm.get_position("a")
        assert pos is not None
        assert 0 <= pos.x <= 40
        assert 0 <= pos.y <= 30

    def test_remove(self) -> None:
        bm = BattleMap(width=60, height=60)
        bm.set_position("a", Position(10, 10))
        bm.remove("a")
        assert bm.get_position("a") is None

    def test_remove_missing_is_noop(self) -> None:
        bm = BattleMap(width=60, height=60)
        bm.remove("nonexistent")  # should not raise


class TestPlaceRandomly:
    def test_all_entities_placed(self) -> None:
        bm = BattleMap(width=60, height=60)
        ids = ["a", "b", "c", "d"]
        bm.place_randomly(ids, rng=random.Random(42))
        for eid in ids:
            assert bm.get_position(eid) is not None

    def test_positions_within_bounds(self) -> None:
        bm = BattleMap(width=40, height=30)
        ids = ["a", "b", "c"]
        bm.place_randomly(ids, rng=random.Random(7))
        for eid in ids:
            pos = bm.get_position(eid)
            assert pos is not None
            assert 0 <= pos.x <= 40
            assert 0 <= pos.y <= 30

    def test_positions_grid_aligned(self) -> None:
        bm = BattleMap(width=60, height=60)
        ids = ["a", "b"]
        bm.place_randomly(ids, rng=random.Random(99))
        for eid in ids:
            pos = bm.get_position(eid)
            assert pos is not None
            assert pos.x % 5 == 0
            assert pos.y % 5 == 0

    def test_no_duplicate_positions(self) -> None:
        bm = BattleMap(width=60, height=60)
        ids = ["a", "b", "c", "d", "e"]
        bm.place_randomly(ids, rng=random.Random(1))
        positions = [bm.get_position(eid) for eid in ids]
        assert len(set(positions)) == len(positions)

    def test_minimum_spacing_respected(self) -> None:
        bm = BattleMap(width=60, height=60)
        ids = ["a", "b"]
        bm.place_randomly(ids, min_spacing=15, rng=random.Random(42))
        pa = bm.get_position("a")
        pb = bm.get_position("b")
        assert pa is not None and pb is not None
        chebyshev = max(abs(pa.x - pb.x), abs(pa.y - pb.y))
        assert chebyshev >= 15

    def test_tiny_map_still_places_all(self) -> None:
        """On a tiny map, spacing may be violated but all entities are placed."""
        bm = BattleMap(width=5, height=5)
        ids = ["a", "b", "c", "d"]
        bm.place_randomly(ids, rng=random.Random(42))
        for eid in ids:
            assert bm.get_position(eid) is not None


class TestWalls:
    """Tests for wall blocking on BattleMap."""

    def test_no_walls_never_blocked(self) -> None:
        bm = BattleMap(width=60, height=60)
        assert not bm.is_step_blocked(Position(10, 10), Position(15, 10))

    def test_vertical_wall_blocks_east_step(self) -> None:
        """Vertical wall at x=20 blocks stepping from (15,10) to (20,10)."""
        bm = BattleMap(width=60, height=60, walls=[Wall(20, 0, 20, 30)])
        assert bm.is_step_blocked(Position(15, 10), Position(20, 10))

    def test_vertical_wall_blocks_west_step(self) -> None:
        """Vertical wall at x=20 blocks stepping from (20,10) to (15,10) too."""
        bm = BattleMap(width=60, height=60, walls=[Wall(20, 0, 20, 30)])
        assert bm.is_step_blocked(Position(20, 10), Position(15, 10))

    def test_vertical_wall_does_not_block_outside_range(self) -> None:
        """Vertical wall y=0..20 does not block at y=25."""
        bm = BattleMap(width=60, height=60, walls=[Wall(20, 0, 20, 20)])
        assert not bm.is_step_blocked(Position(15, 25), Position(20, 25))

    def test_horizontal_wall_blocks_north_step(self) -> None:
        """Horizontal wall at y=30 blocks stepping from (10,25) to (10,30)."""
        bm = BattleMap(width=60, height=60, walls=[Wall(0, 30, 30, 30)])
        assert bm.is_step_blocked(Position(10, 25), Position(10, 30))

    def test_horizontal_wall_blocks_south_step(self) -> None:
        bm = BattleMap(width=60, height=60, walls=[Wall(0, 30, 30, 30)])
        assert bm.is_step_blocked(Position(10, 30), Position(10, 25))

    def test_horizontal_wall_does_not_block_outside_range(self) -> None:
        bm = BattleMap(width=60, height=60, walls=[Wall(0, 30, 20, 30)])
        assert not bm.is_step_blocked(Position(25, 25), Position(25, 30))

    def test_diagonal_step_blocked_when_both_paths_blocked(self) -> None:
        """Diagonal blocked only when BOTH cardinal projections are blocked."""
        # L-shaped wall blocks both horizontal and vertical components
        bm = BattleMap(
            width=60,
            height=60,
            walls=[Wall(20, 0, 20, 30), Wall(0, 20, 30, 20)],
        )
        # Stepping from (15,15) to (20,20): both (15,15)→(20,15) and (15,15)→(15,20) blocked
        assert bm.is_step_blocked(Position(15, 15), Position(20, 20))

    def test_diagonal_step_not_blocked_when_one_path_open(self) -> None:
        """Diagonal NOT blocked when at least one cardinal path is open."""
        # Vertical wall at x=20, y=0..15 — only covers y=0..15, not y=15..20
        # Stepping from (15,15) to (20,20):
        # Path H: (15,15)→(20,15) blocked (wall at x=20, y range includes 15)
        # Path V: (15,15)→(15,20) OK, then (15,20)→(20,20) OK (wall only to y=15)
        # One path open → diagonal allowed
        bm = BattleMap(width=60, height=60, walls=[Wall(20, 0, 20, 15)])
        assert not bm.is_step_blocked(Position(15, 15), Position(20, 20))

    def test_gap_in_wall_allows_passage(self) -> None:
        """Wall with a gap allows movement through the gap."""
        # Wall from y=0 to y=20, then y=30 to y=60 — gap at y=20..30
        bm = BattleMap(
            width=60,
            height=60,
            walls=[Wall(20, 0, 20, 20), Wall(20, 30, 20, 60)],
        )
        # Blocked in wall range
        assert bm.is_step_blocked(Position(15, 10), Position(20, 10))
        # Open in gap
        assert not bm.is_step_blocked(Position(15, 25), Position(20, 25))

    def test_describe_walls(self) -> None:
        bm = BattleMap(
            width=60,
            height=60,
            walls=[Wall(20, 0, 20, 40), Wall(0, 30, 40, 30)],
        )
        descriptions = bm.describe_walls()
        assert len(descriptions) == 3  # arena boundary + 2 inner walls
        assert "60x60" in descriptions[0]
        assert "вертикальная" in descriptions[1]
        assert "горизонтальная" in descriptions[2]

    def test_describe_walls_no_inner_walls(self) -> None:
        bm = BattleMap(width=40, height=40)
        descriptions = bm.describe_walls()
        assert len(descriptions) == 1
        assert "40x40" in descriptions[0]
