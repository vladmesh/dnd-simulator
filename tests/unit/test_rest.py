"""Tests for Long Rest and Short Rest actions."""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.action_defs import CombatMode, get_action_def
from dnd_simulator.core.character import Creature
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.rules.validation import ActionContext, validate_action


def _creature(
    *pools: ResourcePool,
    hp: int = 10,
    max_hp: int = 20,
    in_combat: bool = False,
) -> Creature:
    c = Creature(id="test", name="Test", location_id="arena", max_hp=max_hp, current_hp=hp, ac=10)
    c.resource_pools = list(pools)
    c.in_combat = in_combat
    return c


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


class TestLongRestHandler:
    def test_long_rest_resets_all_resource_pools(self) -> None:
        """Long rest resets both SHORT_REST and LONG_REST pools."""
        from dnd_simulator.rules.handlers.rest import handle_long_rest

        short_pool = ResourcePool("second_wind", 1, 0, RestType.SHORT_REST)
        long_pool = ResourcePool("spell_slot_1", 2, 0, RestType.LONG_REST)
        creature = _creature(short_pool, long_pool)

        ctx = ActionContext(is_combat=False)
        world = _stub_world()
        result = handle_long_rest(creature, Action(name=ActionType.LONG_REST), lambda *a: None, ctx, world)

        assert result.success
        assert short_pool.current_uses == 1
        assert long_pool.current_uses == 2

    def test_long_rest_heals_to_full(self) -> None:
        """Long rest restores HP to max_hp."""
        from dnd_simulator.rules.handlers.rest import handle_long_rest

        creature = _creature(hp=5, max_hp=20)
        ctx = ActionContext(is_combat=False)
        world = _stub_world()
        handle_long_rest(creature, Action(name=ActionType.LONG_REST), lambda *a: None, ctx, world)

        assert creature.current_hp == creature.max_hp

    def test_long_rest_advances_8_hours(self) -> None:
        """Long rest sets wake_at_seconds 8 hours ahead and marks dormant."""
        from dnd_simulator.rules.handlers.rest import handle_long_rest

        creature = _creature()
        ctx = ActionContext(is_combat=False)
        world = _stub_world(time_seconds=10000)
        handle_long_rest(creature, Action(name=ActionType.LONG_REST), lambda *a: None, ctx, world)

        assert creature.wake_at_seconds == 10000 + 8 * 3600
        assert creature.active is False


class TestShortRestHandler:
    def test_short_rest_resets_only_short_rest_pools(self) -> None:
        """Short rest resets SHORT_REST pools, leaves LONG_REST pools untouched."""
        from dnd_simulator.rules.handlers.rest import handle_short_rest

        short_pool = ResourcePool("second_wind", 1, 0, RestType.SHORT_REST)
        long_pool = ResourcePool("spell_slot_1", 2, 0, RestType.LONG_REST)
        creature = _creature(short_pool, long_pool)

        ctx = ActionContext(is_combat=False)
        world = _stub_world()
        result = handle_short_rest(creature, Action(name=ActionType.SHORT_REST), lambda *a: None, ctx, world)

        assert result.success
        assert short_pool.current_uses == 1
        assert long_pool.current_uses == 0  # NOT reset

    def test_short_rest_does_not_heal(self) -> None:
        """Short rest does NOT restore HP."""
        from dnd_simulator.rules.handlers.rest import handle_short_rest

        creature = _creature(hp=5, max_hp=20)
        ctx = ActionContext(is_combat=False)
        world = _stub_world()
        handle_short_rest(creature, Action(name=ActionType.SHORT_REST), lambda *a: None, ctx, world)

        assert creature.current_hp == 5

    def test_short_rest_advances_1_hour(self) -> None:
        """Short rest sets wake_at_seconds 1 hour ahead and marks dormant."""
        from dnd_simulator.rules.handlers.rest import handle_short_rest

        creature = _creature()
        ctx = ActionContext(is_combat=False)
        world = _stub_world(time_seconds=10000)
        handle_short_rest(creature, Action(name=ActionType.SHORT_REST), lambda *a: None, ctx, world)

        assert creature.wake_at_seconds == 10000 + 3600
        assert creature.active is False


# ---------------------------------------------------------------------------
# Validation: rest blocked in combat
# ---------------------------------------------------------------------------


class TestRestBlockedInCombat:
    def test_long_rest_blocked_in_combat(self) -> None:
        """Long rest is PEACEFUL_ONLY — cannot be used in combat."""
        creature = _creature(in_combat=True)
        action = Action(name=ActionType.LONG_REST)
        ctx = ActionContext(is_combat=True)
        error = validate_action(creature, action, ctx)
        assert error is not None
        assert error.code == "WRONG_MODE"

    def test_short_rest_blocked_in_combat(self) -> None:
        """Short rest is PEACEFUL_ONLY — cannot be used in combat."""
        creature = _creature(in_combat=True)
        action = Action(name=ActionType.SHORT_REST)
        ctx = ActionContext(is_combat=True)
        error = validate_action(creature, action, ctx)
        assert error is not None
        assert error.code == "WRONG_MODE"


# ---------------------------------------------------------------------------
# Action provider: rest available out of combat, hidden in combat
# ---------------------------------------------------------------------------


class TestRestActionProvider:
    def test_rest_available_out_of_combat(self) -> None:
        """Rest actions should be offered when creature is not in combat."""
        creature = _creature()
        ctx = ActionContext(is_combat=False)

        # Rest actions are not provider_managed, so BaseActionProvider handles them.
        # Just verify they pass validation.
        for at in (ActionType.LONG_REST, ActionType.SHORT_REST):
            error = validate_action(creature, Action(name=at), ctx)
            assert error is None, f"{at} should be valid out of combat"

    def test_rest_hidden_in_combat(self) -> None:
        """Rest actions should not be offered in combat."""
        creature = _creature(in_combat=True)
        ctx = ActionContext(is_combat=True)

        for at in (ActionType.LONG_REST, ActionType.SHORT_REST):
            error = validate_action(creature, Action(name=at), ctx)
            assert error is not None, f"{at} should be blocked in combat"


# ---------------------------------------------------------------------------
# ActionDef registration check
# ---------------------------------------------------------------------------


class TestRestActionDefs:
    def test_long_rest_action_def(self) -> None:
        d = get_action_def(ActionType.LONG_REST)
        assert d.combat_mode == CombatMode.PEACEFUL_ONLY
        assert d.ends_peaceful_turn is True

    def test_short_rest_action_def(self) -> None:
        d = get_action_def(ActionType.SHORT_REST)
        assert d.combat_mode == CombatMode.PEACEFUL_ONLY
        assert d.ends_peaceful_turn is True


# ---------------------------------------------------------------------------
# Stub world for handler tests
# ---------------------------------------------------------------------------


class _StubTime:
    def __init__(self, seconds: int) -> None:
        self._seconds = seconds

    def to_total_seconds(self) -> int:
        return self._seconds


class _StubWorld:
    def __init__(self, time_seconds: int = 0) -> None:
        self.time = _StubTime(time_seconds)


def _stub_world(time_seconds: int = 0) -> object:
    return _StubWorld(time_seconds)
