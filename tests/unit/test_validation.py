"""Tests for action validation — precondition checks."""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.rules.validation import (
    ActionContext,
    check_action_mode,
    check_actor_active,
    check_actor_alive,
    validate_action,
)


def _creature(*, alive: bool = True, active: bool = True) -> Creature:
    c = Creature(id="test", name="Test", location_id="loc")
    if not alive:
        c.current_hp = 0
    if not active:
        c.active = False
    return c


_COMBAT = ActionContext(is_combat=True, current_turn_entity_id="test")
_PEACEFUL = ActionContext(is_combat=False, current_turn_entity_id="test")


# ---------------------------------------------------------------------------
# check_actor_alive
# ---------------------------------------------------------------------------


class TestCheckActorAlive:
    def test_alive_passes(self) -> None:
        assert check_actor_alive(_creature(), Action(name=ActionType.ATTACK), _COMBAT) is None

    def test_dead_fails(self) -> None:
        error = check_actor_alive(_creature(alive=False), Action(name=ActionType.ATTACK), _COMBAT)
        assert error is not None
        assert error.code == "DEAD_ACTOR"

    def test_dead_fails_any_action(self) -> None:
        for action_type in (
            ActionType.IDLE,
            ActionType.SAY,
            ActionType.ATTACK,
            ActionType.DODGE,
            ActionType.FLEE,
            ActionType.MOVE,
        ):
            error = check_actor_alive(_creature(alive=False), Action(name=action_type), _COMBAT)
            assert error is not None


# ---------------------------------------------------------------------------
# check_actor_active
# ---------------------------------------------------------------------------


class TestCheckActorActive:
    def test_active_passes(self) -> None:
        assert check_actor_active(_creature(), Action(name=ActionType.ATTACK), _COMBAT) is None

    def test_dormant_fails(self) -> None:
        error = check_actor_active(_creature(active=False), Action(name=ActionType.ATTACK), _COMBAT)
        assert error is not None
        assert error.code == "DORMANT_ACTOR"


# ---------------------------------------------------------------------------
# check_action_mode
# ---------------------------------------------------------------------------


class TestCheckActionMode:
    def test_attack_in_combat_ok(self) -> None:
        assert check_action_mode(_creature(), Action(name=ActionType.ATTACK), _COMBAT) is None

    def test_attack_in_peaceful_ok(self) -> None:
        # attack can initiate combat from peaceful
        assert check_action_mode(_creature(), Action(name=ActionType.ATTACK), _PEACEFUL) is None

    def test_dodge_in_combat_ok(self) -> None:
        assert check_action_mode(_creature(), Action(name=ActionType.DODGE), _COMBAT) is None

    def test_dodge_outside_combat_fails(self) -> None:
        error = check_action_mode(_creature(), Action(name=ActionType.DODGE), _PEACEFUL)
        assert error is not None
        assert error.code == "WRONG_MODE"

    def test_flee_outside_combat_fails(self) -> None:
        error = check_action_mode(_creature(), Action(name=ActionType.FLEE), _PEACEFUL)
        assert error is not None
        assert error.code == "WRONG_MODE"

    def test_dash_outside_combat_fails(self) -> None:
        error = check_action_mode(_creature(), Action(name=ActionType.DASH), _PEACEFUL)
        assert error is not None
        assert error.code == "WRONG_MODE"

    def test_say_in_combat_fails(self) -> None:
        error = check_action_mode(_creature(), Action(name=ActionType.SAY), _COMBAT)
        assert error is not None
        assert error.code == "WRONG_MODE"

    def test_say_in_peaceful_ok(self) -> None:
        assert check_action_mode(_creature(), Action(name=ActionType.SAY), _PEACEFUL) is None

    def test_idle_blocked_in_combat(self) -> None:
        assert check_action_mode(_creature(), Action(name=ActionType.IDLE), _COMBAT) is not None
        assert check_action_mode(_creature(), Action(name=ActionType.IDLE), _PEACEFUL) is None

    def test_wait_blocked_in_combat(self) -> None:
        assert check_action_mode(_creature(), Action(name=ActionType.WAIT), _COMBAT) is not None
        assert check_action_mode(_creature(), Action(name=ActionType.WAIT), _PEACEFUL) is None

    def test_move_anywhere_ok(self) -> None:
        assert check_action_mode(_creature(), Action(name=ActionType.MOVE), _COMBAT) is None
        assert check_action_mode(_creature(), Action(name=ActionType.MOVE), _PEACEFUL) is None


# ---------------------------------------------------------------------------
# validate_action (full chain)
# ---------------------------------------------------------------------------


class TestValidateAction:
    def test_valid_combat_attack(self) -> None:
        assert validate_action(_creature(), Action(name=ActionType.ATTACK), _COMBAT) is None

    def test_dead_short_circuits(self) -> None:
        error = validate_action(_creature(alive=False), Action(name=ActionType.ATTACK), _COMBAT)
        assert error is not None
        assert error.code == "DEAD_ACTOR"

    def test_dormant_after_alive(self) -> None:
        error = validate_action(_creature(active=False), Action(name=ActionType.ATTACK), _COMBAT)
        assert error is not None
        assert error.code == "DORMANT_ACTOR"

    def test_wrong_mode_after_alive_and_active(self) -> None:
        error = validate_action(_creature(), Action(name=ActionType.DODGE), _PEACEFUL)
        assert error is not None
        assert error.code == "WRONG_MODE"

    def test_unknown_action_passes(self) -> None:
        # Unknown actions pass validation (fail-safe: don't block gameplay)
        assert validate_action(_creature(), Action(name="unknown_spell"), _COMBAT) is None
