"""Coverage for coincident directions and movement stopping conditions."""

import pytest

from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.rules.movement import (
    _step_toward,
    calculate_away_direction,
    calculate_direction,
    move_direction,
)


@pytest.mark.parametrize("position", [Position(0, 0), Position(15, 20)])
def test_coincident_positions_have_no_toward_direction_and_default_escape(position: Position) -> None:
    target = Position(position.x, position.y)

    assert calculate_direction(position, target) == ""
    assert calculate_away_direction(position, target) == "north"


@pytest.mark.parametrize("target", [Position(10, 10), Position(15, 10), Position(20, 15)])
def test_step_toward_stops_at_target_with_movement_remaining(target: Position) -> None:
    bm = BattleMap(width=100, height=100)

    result = _step_toward(Position(10, 10), target, speed=30, battle_map=bm)

    assert result == target


@pytest.mark.parametrize(
    ("speed", "offset"),
    [(4, 0), (5, 5), (14, 5), (15, 10), (19, 10), (20, 15), (29, 15), (30, 20)],
)
def test_diagonal_movement_requires_enough_budget_for_each_step(speed: int, offset: int) -> None:
    bm = BattleMap(width=100, height=100)

    result = move_direction(Position(10, 10), "northeast", speed=speed, battle_map=bm)

    assert result == Position(10 + offset, 10 + offset)
