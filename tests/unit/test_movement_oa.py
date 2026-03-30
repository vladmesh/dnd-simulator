"""Tests for OA wiring into movement handlers.

Sprint 012, Phase 2, Task 2: movement handlers call on_leave_reach callback
when mover leaves a reactor's weapon reach.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.handlers.movement import handle_move, handle_move_to
from dnd_simulator.rules.validation import ActionContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _creature(id: str, *, hp: int = 20, speed: int = 30, disengaging: bool = False) -> Creature:
    c = Creature(id=id, name=id.capitalize(), location_id="arena", max_hp=hp, current_hp=hp, speed=speed)
    c.turn_budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=speed, reaction=1)
    c.is_disengaging = disengaging
    return c


def _battle_map(width: int = 50, height: int = 50) -> BattleMap:
    return BattleMap(width=width, height=height)


def _combat_state(bm: BattleMap, creature_ids: list[str]) -> CombatState:
    return CombatState(
        location_id="arena",
        turn_order=creature_ids,
        round_number=1,
        rounds_without_attack=0,
        battle_map=bm,
    )


def _ctx(
    combat_state: CombatState,
    mover: Creature,
    entities: dict[str, Creature],
    on_leave_reach: object | None = None,
) -> ActionContext:
    return ActionContext(
        is_combat=True,
        current_turn_entity_id=mover.id,
        turn_budget=mover.turn_budget,
        combat_state=combat_state,
        get_entity=lambda id: entities.get(id),
        on_leave_reach=on_leave_reach,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# handle_move_to + OA
# ---------------------------------------------------------------------------


class TestHandleMoveToOA:
    def test_callback_called_when_leaving_reach(self) -> None:
        """Mover walks past an enemy; callback fired when leaving reach."""
        mover = _creature("mover")
        guard = _creature("guard")

        bm = _battle_map()
        # Guard at (10,5), mover at (10,10). Distance=5ft (in reach).
        # Mover goes to (10,25). At step (10,10)→(10,15): distance becomes 10ft. Trigger!
        bm.set_position("mover", Position(10, 10))
        bm.set_position("guard", Position(10, 5))
        cs = _combat_state(bm, ["mover", "guard"])

        callback = MagicMock(return_value=True)
        entities = {"mover": mover, "guard": guard}
        ctx = _ctx(cs, mover, entities, on_leave_reach=callback)

        action = Action(name=ActionType.MOVE_TO, params={"x": 10, "y": 25})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_move_to(mover, action, emit_fn, ctx, world)

        assert result.success
        callback.assert_called_once()
        call_args = callback.call_args
        assert call_args[0][0] is mover
        assert call_args[0][1] == Position(10, 10)  # from (in reach)
        assert call_args[0][2] == Position(10, 15)  # to (out of reach)
        assert guard in call_args[0][3]

    def test_movement_stops_when_mover_dies(self) -> None:
        """Callback returns False (mover dead) — movement stops at death position."""
        mover = _creature("mover", hp=1)
        guard = _creature("guard")

        bm = _battle_map()
        bm.set_position("mover", Position(10, 10))
        bm.set_position("guard", Position(10, 5))
        cs = _combat_state(bm, ["mover", "guard"])

        def kill_callback(m: Creature, from_pos: Position, to_pos: Position, reactors: list[Creature]) -> bool:
            m.current_hp = 0
            return False

        entities = {"mover": mover, "guard": guard}
        ctx = _ctx(cs, mover, entities, on_leave_reach=kill_callback)

        action = Action(name=ActionType.MOVE_TO, params={"x": 10, "y": 25})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        handle_move_to(mover, action, emit_fn, ctx, world)

        # Mover stays at (10,10) — last position where still in reach, before the lethal step
        assert bm.get_position("mover") == Position(10, 10)

    def test_disengaging_prevents_callback(self) -> None:
        """Mover with is_disengaging=True — no OA triggers, full movement."""
        mover = _creature("mover", disengaging=True)
        guard = _creature("guard")

        bm = _battle_map()
        bm.set_position("mover", Position(10, 10))
        bm.set_position("guard", Position(10, 5))
        cs = _combat_state(bm, ["mover", "guard"])

        callback = MagicMock(return_value=True)
        entities = {"mover": mover, "guard": guard}
        ctx = _ctx(cs, mover, entities, on_leave_reach=callback)

        action = Action(name=ActionType.MOVE_TO, params={"x": 10, "y": 25})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_move_to(mover, action, emit_fn, ctx, world)

        assert result.success
        callback.assert_not_called()
        assert bm.get_position("mover") == Position(10, 25)

    def test_two_enemies_two_callbacks(self) -> None:
        """Two enemies at different positions — callback called twice."""
        mover = _creature("mover")
        guard_a = _creature("guard_a")
        guard_b = _creature("guard_b")

        bm = _battle_map()
        # Mover path: (10,5)→(10,10)→(10,15)→(10,20)→(10,25)
        # Guard A at (10,0): in reach at (10,5), out at (10,10). Trigger step 0.
        # Guard B at (15,15): in reach at (10,20) via diagonal 5ft,
        #   out at (10,25) → dist max(1,2)*5=10ft. Trigger step 3.
        bm.set_position("mover", Position(10, 5))
        bm.set_position("guard_a", Position(10, 0))
        bm.set_position("guard_b", Position(15, 15))
        cs = _combat_state(bm, ["mover", "guard_a", "guard_b"])

        callback = MagicMock(return_value=True)
        entities = {"mover": mover, "guard_a": guard_a, "guard_b": guard_b}
        ctx = _ctx(cs, mover, entities, on_leave_reach=callback)

        action = Action(name=ActionType.MOVE_TO, params={"x": 10, "y": 25})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_move_to(mover, action, emit_fn, ctx, world)

        assert result.success
        assert callback.call_count == 2


# ---------------------------------------------------------------------------
# handle_move (direction) + OA
# ---------------------------------------------------------------------------


class TestHandleMoveDirectionOA:
    def test_callback_called_when_leaving_reach(self) -> None:
        """Single step south leaves enemy reach — callback called."""
        mover = _creature("mover")
        guard = _creature("guard")

        bm = _battle_map()
        bm.set_position("mover", Position(10, 10))
        bm.set_position("guard", Position(10, 15))
        # Moving south (y-=5): (10,10)→(10,5). Guard dist 5→10ft. Leaves reach.
        cs = _combat_state(bm, ["mover", "guard"])

        callback = MagicMock(return_value=True)
        entities = {"mover": mover, "guard": guard}
        ctx = _ctx(cs, mover, entities, on_leave_reach=callback)

        action = Action(name=ActionType.MOVE, params={"direction": "south", "ft": 5})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_move(mover, action, emit_fn, ctx, world)

        assert result.success
        callback.assert_called_once()
        call_args = callback.call_args
        assert call_args[0][0] is mover
        assert call_args[0][1] == Position(10, 10)  # from
        assert call_args[0][2] == Position(10, 5)  # to
        assert guard in call_args[0][3]

    def test_no_callback_when_none(self) -> None:
        """Non-combat move (on_leave_reach=None) — works as before."""
        mover = _creature("mover")

        bm = _battle_map()
        bm.set_position("mover", Position(10, 10))
        cs = _combat_state(bm, ["mover"])

        entities = {"mover": mover}
        ctx = _ctx(cs, mover, entities, on_leave_reach=None)

        action = Action(name=ActionType.MOVE, params={"direction": "south", "ft": 5})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_move(mover, action, emit_fn, ctx, world)

        assert result.success

    def test_movement_stops_when_mover_dies(self) -> None:
        """Callback returns False — mover stays at original position."""
        mover = _creature("mover", hp=1)
        guard = _creature("guard")

        bm = _battle_map()
        bm.set_position("mover", Position(10, 10))
        bm.set_position("guard", Position(10, 15))
        cs = _combat_state(bm, ["mover", "guard"])

        def kill_callback(m: Creature, from_pos: Position, to_pos: Position, reactors: list[Creature]) -> bool:
            m.current_hp = 0
            return False

        entities = {"mover": mover, "guard": guard}
        ctx = _ctx(cs, mover, entities, on_leave_reach=kill_callback)

        action = Action(name=ActionType.MOVE, params={"direction": "south", "ft": 5})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        handle_move(mover, action, emit_fn, ctx, world)

        assert bm.get_position("mover") == Position(10, 10)
