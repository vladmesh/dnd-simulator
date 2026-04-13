"""Tests for Action Surge — Fighter L2 bonus action granting extra Action."""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Character, CharClass, Creature, Race
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle
from dnd_simulator.core.models import ActionResult, Event
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.action_provider import ClassFeatureActionProvider
from dnd_simulator.rules.actions import action_cost
from dnd_simulator.rules.handlers import handle_action_surge
from dnd_simulator.rules.resources import has_resource, reset_resources
from dnd_simulator.rules.validation import ActionContext, validate_action


def _fighter(*, level: int = 2, pool_uses: int = 1) -> Character:
    pools = [ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)]
    if level >= 2:
        pools.append(ResourcePool("action_surge", 1, pool_uses, RestType.SHORT_REST))
    return Character(
        id="fighter",
        name="Fighter",
        location_id="arena",
        max_hp=20,
        current_hp=20,
        ac=16,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=level,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        resource_pools=pools,
    )


def _fighter_l1() -> Character:
    return Character(
        id="fighter1",
        name="FighterL1",
        location_id="arena",
        max_hp=20,
        current_hp=20,
        ac=16,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=1,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        resource_pools=[ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)],
    )


def _ctx(*, is_combat: bool = True, budget: TurnBudget | None = None) -> ActionContext:
    return ActionContext(
        is_combat=is_combat,
        turn_budget=budget or TurnBudget(actions=1, bonus_actions=1, movement_remaining=30),
    )


def _noop_emit(event: Event) -> ActionResult:
    return ActionResult()


class TestActionSurgeCost:
    def test_is_bonus_action(self) -> None:
        cost = action_cost(Action(name=ActionType.ACTION_SURGE))
        assert cost.bonus_actions == 1
        assert cost.actions == 0


class TestActionSurgeHandler:
    def test_grants_extra_action(self) -> None:
        fighter = _fighter()
        budget = TurnBudget(actions=0, bonus_actions=1, movement_remaining=30)
        ctx = _ctx(budget=budget)
        result = handle_action_surge(fighter, Action(name=ActionType.ACTION_SURGE), _noop_emit, ctx, None)  # type: ignore[arg-type]
        assert result.success
        assert budget.actions == 1
        assert has_resource(fighter, "action_surge") is False

    def test_consumes_resource(self) -> None:
        fighter = _fighter()
        ctx = _ctx()
        handle_action_surge(fighter, Action(name=ActionType.ACTION_SURGE), _noop_emit, ctx, None)  # type: ignore[arg-type]
        assert has_resource(fighter, "action_surge") is False

    def test_non_character_fails(self) -> None:
        creature = Creature(id="wolf", name="Wolf", location_id="arena", max_hp=10, current_hp=5, ac=13)
        result = handle_action_surge(creature, Action(name=ActionType.ACTION_SURGE), _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False


class TestActionSurgeProvider:
    def test_available_for_fighter_l2(self) -> None:
        fighter = _fighter(level=2, pool_uses=1)
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(fighter, _ctx())
        assert ActionType.ACTION_SURGE in actions

    def test_not_available_for_fighter_l1(self) -> None:
        fighter = _fighter_l1()
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(fighter, _ctx())
        assert ActionType.ACTION_SURGE not in actions

    def test_not_available_when_exhausted(self) -> None:
        fighter = _fighter(level=2, pool_uses=0)
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(fighter, _ctx())
        assert ActionType.ACTION_SURGE not in actions

    def test_not_available_for_rogue(self) -> None:
        rogue = Character(
            id="rogue",
            name="Rogue",
            location_id="arena",
            max_hp=15,
            current_hp=10,
            ac=14,
            race=Race.HUMAN,
            char_class=CharClass.ROGUE,
            level=2,
        )
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(rogue, _ctx())
        assert ActionType.ACTION_SURGE not in actions


class TestActionSurgeValidation:
    def test_l1_fighter_handler_rejects(self) -> None:
        fighter = _fighter_l1()
        result = handle_action_surge(fighter, Action(name=ActionType.ACTION_SURGE), _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False

    def test_l2_fighter_passes_validation(self) -> None:
        fighter = _fighter(level=2)
        error = validate_action(fighter, Action(name=ActionType.ACTION_SURGE), _ctx())
        assert error is None

    def test_blocked_outside_combat(self) -> None:
        fighter = _fighter(level=2)
        error = validate_action(fighter, Action(name=ActionType.ACTION_SURGE), _ctx(is_combat=False))
        assert error is not None


class TestActionSurgeReset:
    def test_resets_on_short_rest(self) -> None:
        fighter = _fighter(level=2, pool_uses=0)
        reset_ids = reset_resources(fighter, RestType.SHORT_REST)
        assert "action_surge" in reset_ids
        assert has_resource(fighter, "action_surge") is True
