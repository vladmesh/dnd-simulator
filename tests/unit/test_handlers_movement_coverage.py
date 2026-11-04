"""Movement budget changes while resolving opportunity attacks."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from test_handlers_movement import _combat_state, _creature

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.core.events import EntityMovePayload
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.core.turn_budget import ActionCost
from dnd_simulator.rules.handlers.movement import handle_move_to
from dnd_simulator.rules.validation import ActionContext


@pytest.mark.parametrize(
    ("movement_penalty", "expected_x", "expected_remaining"),
    [(25, 10, 0), (20, 15, 0), (18, 15, 2), (0, 25, 10)],
)
def test_move_to_rechecks_budget_after_opportunity_attack(
    movement_penalty: int, expected_x: int, expected_remaining: int
) -> None:
    mover = _creature("mover")
    guard = _creature("guard")
    budget = mover.turn_budget
    assert budget is not None
    bm = BattleMap(width=30, height=10)
    bm.set_position(mover.id, Position(5, 0))
    bm.set_position(guard.id, Position(0, 0))
    combat = _combat_state(bm, [mover.id, guard.id])
    entities = {mover.id: mover, guard.id: guard}
    events: list[Event] = []

    def on_leave_reach(actor: Creature, from_pos: Position, to_pos: Position, reactors: list[Creature]) -> bool:
        assert actor is mover
        assert (from_pos, to_pos) == (Position(5, 0), Position(10, 0))
        assert reactors == [guard]
        assert guard.turn_budget is not None
        guard.turn_budget.consume(ActionCost(reaction=1))
        budget.consume(ActionCost(movement_ft=movement_penalty))
        return actor.is_alive

    def emit_fn(event: Event) -> ActionResult:
        events.append(event)
        return ActionResult()

    ctx = ActionContext(
        is_combat=True,
        current_turn_entity_id=mover.id,
        turn_budget=budget,
        combat_state=combat,
        get_entity=entities.get,
        on_leave_reach=on_leave_reach,
    )

    result = handle_move_to(
        mover,
        Action(name=ActionType.MOVE_TO, params={"x": 25, "y": 0}),
        emit_fn,
        ctx,
        MagicMock(),
    )

    assert result.success
    assert mover.is_alive
    assert bm.get_position(mover.id) == Position(expected_x, 0)
    assert budget.movement_remaining == expected_remaining
    assert budget.actions == 1
    assert guard.turn_budget is not None
    assert guard.turn_budget.reaction == 0
    assert len(events) == 1
    assert events[0].event_type == EventType.ENTITY_MOVE
    assert events[0].data == EntityMovePayload(mover.id, "arena", 5, 0, expected_x, 0, expected_x - 5)
