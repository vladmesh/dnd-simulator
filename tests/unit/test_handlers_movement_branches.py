"""Branch coverage for rules/handlers/movement.py: move/move_to/travel rejection paths."""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.location import Location, LocationEdge, LocationGraph
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.handlers.movement import handle_move, handle_move_to, handle_travel
from dnd_simulator.rules.validation import ActionContext


def _creature() -> Creature:
    creature = Creature(id="mover", name="Mover", location_id="arena", max_hp=10, current_hp=10, speed=30)
    creature.turn_budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30, reaction=1)
    return creature


def _combat(bm: BattleMap) -> CombatState:
    return CombatState(
        location_id="arena", turn_order=["mover"], round_number=1, rounds_without_attack=0, battle_map=bm
    )


def _ctx(
    creature: Creature, combat: CombatState | None, budget: TurnBudget | None, on_leave_reach: object | None = None
) -> ActionContext:
    return ActionContext(
        is_combat=combat is not None,
        current_turn_entity_id=creature.id,
        turn_budget=budget,
        combat_state=combat,
        get_entity=lambda eid: creature if eid == creature.id else None,
        on_leave_reach=on_leave_reach,  # type: ignore[arg-type]
    )


def _move_to(x: int, y: int) -> Action:
    return Action(name=ActionType.MOVE_TO, params={"x": x, "y": y})


class TestHandleMove:
    def test_combatant_off_the_map_cannot_move(self) -> None:
        mover = _creature()
        ctx = _ctx(mover, _combat(BattleMap(width=10, height=10)), mover.turn_budget, MagicMock(return_value=True))
        emit_fn = MagicMock(return_value=ActionResult())

        result = handle_move(
            mover, Action(name=ActionType.MOVE, params={"direction": "north"}), emit_fn, ctx, MagicMock()
        )

        assert result.success is False
        emit_fn.assert_not_called()


class TestHandleMoveTo:
    def test_no_budget_rejected(self) -> None:
        mover = _creature()
        result = handle_move_to(mover, _move_to(1, 1), MagicMock(), _ctx(mover, None, None), MagicMock())
        assert result.success is False

    def test_outside_combat_rejected(self) -> None:
        mover = _creature()
        result = handle_move_to(mover, _move_to(1, 1), MagicMock(), _ctx(mover, None, mover.turn_budget), MagicMock())
        assert result.success is False

    def test_off_the_map_rejected(self) -> None:
        mover = _creature()
        ctx = _ctx(mover, _combat(BattleMap(width=10, height=10)), mover.turn_budget)
        result = handle_move_to(mover, _move_to(1, 1), MagicMock(), ctx, MagicMock())
        assert result.success is False

    def test_target_is_current_cell_rejected(self) -> None:
        mover = _creature()
        bm = BattleMap(width=10, height=10)
        bm.set_position("mover", Position(3, 3))
        budget = mover.turn_budget
        assert budget is not None

        result = handle_move_to(mover, _move_to(3, 3), MagicMock(), _ctx(mover, _combat(bm), budget), MagicMock())

        assert result.success is False
        assert budget.movement_remaining == 30


class TestHandleTravel:
    def _world(self) -> MagicMock:
        world = MagicMock()
        world.location_graph = LocationGraph(
            [
                Location(id="arena", name="Arena", region_id="r", edges=(LocationEdge("town", 1000),)),
                Location(id="town", name="Town", region_id="r", edges=(LocationEdge("arena", 1000),)),
            ]
        )
        return world

    def test_missing_destination_rejected(self) -> None:
        mover = _creature()
        result = handle_travel(
            mover, Action(name=ActionType.TRAVEL, params={}), MagicMock(), MagicMock(), self._world()
        )
        assert result.success is False
        assert mover.current_intent is None

    def test_already_at_destination_rejected(self) -> None:
        mover = _creature()
        action = Action(name=ActionType.TRAVEL, params={"destination_id": "arena"})
        result = handle_travel(mover, action, MagicMock(), MagicMock(), self._world())
        assert result.success is False
        assert mover.current_intent is None
