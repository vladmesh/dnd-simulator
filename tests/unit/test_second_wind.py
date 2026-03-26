"""Tests for Second Wind — Fighter bonus action heal."""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import (
    Character,
    CharClass,
    Creature,
    Race,
)
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle
from dnd_simulator.core.models import ActionResult, Event
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.action_provider import ClassFeatureActionProvider
from dnd_simulator.rules.actions import action_cost
from dnd_simulator.rules.handlers import handle_second_wind
from dnd_simulator.rules.resources import has_resource
from dnd_simulator.rules.validation import ActionContext


def _fighter(
    *,
    current_hp: int = 10,
    max_hp: int = 20,
    level: int = 1,
    pool_uses: int = 1,
) -> Character:
    return Character(
        id="fighter",
        name="Fighter",
        location_id="arena",
        max_hp=max_hp,
        current_hp=current_hp,
        ac=16,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=level,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        resource_pools=[ResourcePool("second_wind", 1, pool_uses, RestType.SHORT_REST)],
    )


def _ctx(*, is_combat: bool = True) -> ActionContext:
    return ActionContext(
        is_combat=is_combat,
        turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=30),
    )


def _noop_emit(event: Event) -> ActionResult:
    return ActionResult()


# ---------------------------------------------------------------------------
# Action cost
# ---------------------------------------------------------------------------


class TestSecondWindCost:
    def test_is_bonus_action(self) -> None:
        cost = action_cost(Action(name=ActionType.SECOND_WIND))
        assert cost.bonus_actions == 1
        assert cost.actions == 0


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


class TestSecondWindHandler:
    def test_heals_fighter(self) -> None:
        fighter = _fighter(current_hp=5, max_hp=20, level=1)
        ctx = _ctx()
        # Seed RNG for deterministic roll: 1d10 → need to control
        result = handle_second_wind(fighter, Action(name=ActionType.SECOND_WIND), _noop_emit, ctx, None)  # type: ignore[arg-type]
        assert result.success
        assert fighter.current_hp > 5  # healed at least 1d10(min 1) + 1 = 2
        assert has_resource(fighter, "second_wind") is False  # consumed

    def test_healing_capped_at_max_hp(self) -> None:
        fighter = _fighter(current_hp=19, max_hp=20, level=1)
        handle_second_wind(fighter, Action(name=ActionType.SECOND_WIND), _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert fighter.current_hp == 20  # can't exceed max

    def test_consumes_resource(self) -> None:
        fighter = _fighter(current_hp=5, pool_uses=1)
        handle_second_wind(fighter, Action(name=ActionType.SECOND_WIND), _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert has_resource(fighter, "second_wind") is False

    def test_higher_level_heals_more(self) -> None:
        """Level 5 Fighter heals 1d10 + 5, min healing = 6."""
        fighter = _fighter(current_hp=1, max_hp=50, level=5)
        handle_second_wind(fighter, Action(name=ActionType.SECOND_WIND), _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        # 1d10 + 5 = min 6, max 15
        assert fighter.current_hp >= 7  # 1 + min(6) = 7

    def test_non_character_fails(self) -> None:
        creature = Creature(id="wolf", name="Wolf", location_id="arena", max_hp=10, current_hp=5, ac=13)
        result = handle_second_wind(creature, Action(name=ActionType.SECOND_WIND), _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class TestSecondWindProvider:
    def test_available_for_fighter_with_resource(self) -> None:
        fighter = _fighter(pool_uses=1)
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(fighter, _ctx())
        assert ActionType.SECOND_WIND in actions

    def test_not_available_when_exhausted(self) -> None:
        fighter = _fighter(pool_uses=0)
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(fighter, _ctx())
        assert ActionType.SECOND_WIND not in actions

    def test_not_available_for_non_fighter(self) -> None:
        rogue = Character(
            id="rogue",
            name="Rogue",
            location_id="arena",
            max_hp=15,
            current_hp=10,
            ac=14,
            race=Race.HUMAN,
            char_class=CharClass.ROGUE,
        )
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(rogue, _ctx())
        assert ActionType.SECOND_WIND not in actions

    def test_not_available_for_plain_creature(self) -> None:
        creature = Creature(id="wolf", name="Wolf", location_id="arena", max_hp=10, current_hp=5, ac=13)
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(creature, _ctx())
        assert ActionType.SECOND_WIND not in actions


# ---------------------------------------------------------------------------
# Resource reset
# ---------------------------------------------------------------------------


class TestSecondWindReset:
    def test_resets_on_short_rest(self) -> None:
        from dnd_simulator.rules.resources import reset_resources

        fighter = _fighter(pool_uses=0)
        reset_ids = reset_resources(fighter, RestType.SHORT_REST)
        assert "second_wind" in reset_ids
        assert has_resource(fighter, "second_wind") is True

    def test_resets_on_long_rest(self) -> None:
        from dnd_simulator.rules.resources import reset_resources

        fighter = _fighter(pool_uses=0)
        reset_ids = reset_resources(fighter, RestType.LONG_REST)
        assert "second_wind" in reset_ids
