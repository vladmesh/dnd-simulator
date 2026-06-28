"""Focused unit tests for rules/handlers/movement.py — handle_move, handle_dash, handle_disengage, handle_wait.

Sprint 012, Phase 4, Task 3.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.models import ActionResult, Event
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.i18n import set_language
from dnd_simulator.rules.handlers.movement import handle_dash, handle_disengage, handle_move, handle_wait
from dnd_simulator.rules.validation import ActionContext


def _has_cyrillic(text: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in text)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _creature(id: str, *, hp: int = 20, speed: int = 30) -> Creature:
    c = Creature(id=id, name=id.capitalize(), location_id="arena", max_hp=hp, current_hp=hp, speed=speed)
    c.turn_budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=speed, reaction=1)
    return c


def _battle_map() -> BattleMap:
    return BattleMap(width=50, height=50)


def _combat_state(bm: BattleMap, creature_ids: list[str]) -> CombatState:
    return CombatState(
        location_id="arena",
        turn_order=creature_ids,
        round_number=1,
        rounds_without_attack=0,
        battle_map=bm,
    )


def _ctx(
    creature: Creature,
    combat_state: CombatState | None = None,
    entities: dict[str, Creature] | None = None,
    on_leave_reach: object | None = None,
) -> ActionContext:
    return ActionContext(
        is_combat=combat_state is not None,
        current_turn_entity_id=creature.id,
        turn_budget=creature.turn_budget,
        combat_state=combat_state,
        get_entity=lambda eid: (entities or {}).get(eid),
        on_leave_reach=on_leave_reach,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# handle_move
# ---------------------------------------------------------------------------


class TestHandleMove:
    def test_move_in_combat_updates_position(self) -> None:
        """Move north in combat updates the battle map position."""
        mover = _creature("mover")
        bm = _battle_map()
        bm.set_position("mover", Position(10, 10))
        cs = _combat_state(bm, ["mover"])
        # on_leave_reach must be provided for direct combat resolution
        on_leave_reach = MagicMock(return_value=True)
        ctx = _ctx(mover, combat_state=cs, entities={"mover": mover}, on_leave_reach=on_leave_reach)
        action = Action(name=ActionType.MOVE, params={"direction": "north", "ft": 5})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_move(mover, action, emit_fn, ctx, world)

        assert result.success
        assert bm.get_position("mover") == Position(10, 15)

    def test_move_non_combat_emits_event(self) -> None:
        """Non-combat move emits ENTITY_MOVE event (resolved by CombatManager)."""
        mover = _creature("mover")
        emit_fn = MagicMock(return_value=ActionResult(success=True))
        ctx = _ctx(mover)  # no combat_state
        action = Action(name=ActionType.MOVE, params={"direction": "south", "ft": 5})
        world = MagicMock()

        handle_move(mover, action, emit_fn, ctx, world)

        emit_fn.assert_called_once()
        event = emit_fn.call_args[0][0]
        assert event.data["entity_id"] == "mover"
        assert event.data["direction"] == "south"

    def test_move_missing_direction_fails(self) -> None:
        """Move without direction param fails."""
        mover = _creature("mover")
        ctx = _ctx(mover)
        action = Action(name=ActionType.MOVE, params={})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_move(mover, action, emit_fn, ctx, world)

        assert not result.success
        assert "direction" in result.error.lower()

    def test_move_blocked_at_map_edge_fails(self) -> None:
        """Move south at y=0 goes off-map and fails."""
        mover = _creature("mover")
        bm = _battle_map()
        bm.set_position("mover", Position(10, 0))
        cs = _combat_state(bm, ["mover"])
        on_leave_reach = MagicMock(return_value=True)
        ctx = _ctx(mover, combat_state=cs, entities={"mover": mover}, on_leave_reach=on_leave_reach)
        action = Action(name=ActionType.MOVE, params={"direction": "south", "ft": 5})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_move(mover, action, emit_fn, ctx, world)

        # Should fail since south would go to negative y which is off-map
        assert not result.success


class TestMoveErrorI18n:
    """Movement-handler error strings must localize and carry no em-dash."""

    def teardown_method(self) -> None:
        set_language("en")

    def _blocked_move(self) -> ActionResult:
        # Mover at y=0 moving south goes off-map → blocked branch.
        mover = _creature("mover")
        bm = _battle_map()
        bm.set_position("mover", Position(10, 0))
        cs = _combat_state(bm, ["mover"])
        on_leave_reach = MagicMock(return_value=True)
        ctx = _ctx(mover, combat_state=cs, entities={"mover": mover}, on_leave_reach=on_leave_reach)
        action = Action(name=ActionType.MOVE, params={"direction": "south", "ft": 5})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()
        return handle_move(mover, action, emit_fn, ctx, world)

    def test_blocked_move_localizes_russian(self) -> None:
        """Under a RU session the blocked error renders in Russian with no em-dash."""
        set_language("ru")
        result = self._blocked_move()
        assert not result.success
        assert "—" not in result.error
        assert _has_cyrillic(result.error)

    def test_blocked_move_english_plain(self) -> None:
        """Under an EN session the wrapped literal still comes back, comma not em-dash."""
        set_language("en")
        result = self._blocked_move()
        assert not result.success
        assert result.error == "Cannot move there, blocked"


# ---------------------------------------------------------------------------
# handle_dash
# ---------------------------------------------------------------------------


class TestHandleDash:
    def test_adds_speed_to_movement_budget(self) -> None:
        """Dash adds creature's effective speed to movement_remaining."""
        mover = _creature("mover", speed=30)
        assert mover.turn_budget is not None
        initial_movement = mover.turn_budget.movement_remaining
        ctx = _ctx(mover)
        action = Action(name=ActionType.DASH, params={})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_dash(mover, action, emit_fn, ctx, world)

        assert result.success
        assert mover.turn_budget.movement_remaining == initial_movement + 30

    def test_dash_emits_event(self) -> None:
        """Dash emits ENTITY_DASH event with extra_movement_ft."""
        mover = _creature("mover", speed=25)
        ctx = _ctx(mover)
        action = Action(name=ActionType.DASH, params={})
        events: list[Event] = []

        def emit_fn(event: Event) -> ActionResult:
            events.append(event)
            return ActionResult()

        world = MagicMock()
        handle_dash(mover, action, emit_fn, ctx, world)

        assert len(events) == 1
        assert events[0].data["entity_id"] == "mover"
        assert events[0].data["extra_movement_ft"] == 25

    def test_dash_no_budget_fails(self) -> None:
        """Dash with no turn budget fails."""
        mover = _creature("mover")
        mover.turn_budget = None
        ctx = ActionContext(is_combat=True, current_turn_entity_id=mover.id, turn_budget=None)
        action = Action(name=ActionType.DASH, params={})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_dash(mover, action, emit_fn, ctx, world)

        assert not result.success


# ---------------------------------------------------------------------------
# handle_disengage
# ---------------------------------------------------------------------------


class TestHandleDisengage:
    def test_sets_is_disengaging_flag(self) -> None:
        """Disengage sets is_disengaging=True on the creature."""
        mover = _creature("mover")
        assert not mover.is_disengaging
        ctx = _ctx(mover)
        action = Action(name=ActionType.DISENGAGE, params={})
        emit_fn = MagicMock(return_value=ActionResult())
        world = MagicMock()

        result = handle_disengage(mover, action, emit_fn, ctx, world)

        assert result.success
        assert mover.is_disengaging is True

    def test_disengage_emits_event(self) -> None:
        """Disengage emits ENTITY_DISENGAGE event."""
        mover = _creature("mover")
        ctx = _ctx(mover)
        action = Action(name=ActionType.DISENGAGE, params={})
        events: list[Event] = []

        def emit_fn(event: Event) -> ActionResult:
            events.append(event)
            return ActionResult()

        world = MagicMock()
        handle_disengage(mover, action, emit_fn, ctx, world)

        assert len(events) == 1
        assert events[0].data["entity_id"] == "mover"


# ---------------------------------------------------------------------------
# handle_wait
# ---------------------------------------------------------------------------


class TestHandleWait:
    def test_sets_wake_at_and_dormant(self) -> None:
        """Wait sets wake_at_seconds and marks creature dormant."""
        mover = _creature("mover")
        world = MagicMock()
        world.time.to_total_seconds.return_value = 10000
        ctx = _ctx(mover)
        action = Action(name=ActionType.WAIT, params={"hours": 2})
        emit_fn = MagicMock(return_value=ActionResult())

        result = handle_wait(mover, action, emit_fn, ctx, world)

        assert result.success
        assert mover.wake_at_seconds == 10000 + 2 * 3600
        assert mover.active is False

    def test_wait_default_one_hour(self) -> None:
        """Wait without hours param defaults to 1 hour."""
        mover = _creature("mover")
        world = MagicMock()
        world.time.to_total_seconds.return_value = 5000
        ctx = _ctx(mover)
        action = Action(name=ActionType.WAIT, params={})
        emit_fn = MagicMock(return_value=ActionResult())

        handle_wait(mover, action, emit_fn, ctx, world)

        assert mover.wake_at_seconds == 5000 + 3600

    def test_wait_travel(self) -> None:
        """Wait with travel_to changes location and advances time."""
        mover = _creature("mover")
        mover.location_id = "town_square"
        world = MagicMock()
        world.location_graph.travel_seconds.return_value = 600
        ctx = _ctx(mover)
        action = Action(name=ActionType.WAIT, params={"travel_to": "tavern"})
        emit_fn = MagicMock(return_value=ActionResult())

        result = handle_wait(mover, action, emit_fn, ctx, world)

        assert result.success
        assert mover.location_id == "tavern"
        world.advance_time.assert_called_once()
