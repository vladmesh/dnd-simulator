"""Tests for Cunning Action — Rogue Dash/Disengage as bonus action via cost_mode."""

from __future__ import annotations

import pytest

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Character,
    CharClass,
    Creature,
    Race,
)
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle, RogueFeatures
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.actions import action_cost, collect_cost_overrides


def _rogue() -> Character:
    scores = AbilityScores()
    scores[Ability.DEX] = 16
    return Character(
        id="rogue",
        name="Test Rogue",
        location_id="loc",
        ac=14,
        current_hp=20,
        max_hp=20,
        speed=30,
        ability_scores=scores,
        race=Race.HUMAN,
        char_class=CharClass.ROGUE,
        level=1,
        class_features=[RogueFeatures()],
    )


def _fighter() -> Character:
    return Character(
        id="fighter",
        name="Test Fighter",
        location_id="loc",
        ac=16,
        current_hp=30,
        max_hp=30,
        speed=30,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=1,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
    )


def _plain_creature() -> Creature:
    return Creature(
        id="goblin",
        name="Goblin",
        location_id="loc",
        ac=12,
        current_hp=10,
        max_hp=10,
        speed=30,
    )


# ---------------------------------------------------------------------------
# collect_cost_overrides
# ---------------------------------------------------------------------------


class TestCollectCostOverrides:
    def test_rogue_has_cunning_action_overrides(self) -> None:
        overrides = collect_cost_overrides(_rogue())
        assert len(overrides) == 2
        names = {ov.action_type for ov in overrides}
        assert names == {ActionType.DASH, ActionType.DISENGAGE}

    def test_fighter_has_no_overrides(self) -> None:
        assert collect_cost_overrides(_fighter()) == []

    def test_plain_creature_has_no_overrides(self) -> None:
        assert collect_cost_overrides(_plain_creature()) == []


# ---------------------------------------------------------------------------
# action_cost with cost_mode param
# ---------------------------------------------------------------------------


class TestCunningActionCost:
    def test_dash_bonus_with_cost_mode(self) -> None:
        """Rogue explicitly chooses bonus action via cost_mode."""
        cost = action_cost(
            Action(name=ActionType.DASH, params={"cost_mode": "bonus_action"}),
            creature=_rogue(),
        )
        assert cost.bonus_actions == 1
        assert cost.actions == 0

    def test_disengage_bonus_with_cost_mode(self) -> None:
        cost = action_cost(
            Action(name=ActionType.DISENGAGE, params={"cost_mode": "bonus_action"}),
            creature=_rogue(),
        )
        assert cost.bonus_actions == 1
        assert cost.actions == 0

    def test_dash_default_cost_without_cost_mode(self) -> None:
        """Without cost_mode, Rogue pays standard action cost."""
        cost = action_cost(Action(name=ActionType.DASH), creature=_rogue())
        assert cost.actions == 1
        assert cost.bonus_actions == 0

    def test_disengage_default_cost_without_cost_mode(self) -> None:
        cost = action_cost(Action(name=ActionType.DISENGAGE), creature=_rogue())
        assert cost.actions == 1
        assert cost.bonus_actions == 0

    def test_dash_costs_action_for_fighter(self) -> None:
        cost = action_cost(Action(name=ActionType.DASH), creature=_fighter())
        assert cost.actions == 1
        assert cost.bonus_actions == 0

    def test_fighter_cannot_use_bonus_cost_mode(self) -> None:
        """Fighter has no Cunning Action — cost_mode=bonus_action raises."""
        with pytest.raises(ValueError, match="No cost override"):
            action_cost(
                Action(name=ActionType.DASH, params={"cost_mode": "bonus_action"}),
                creature=_fighter(),
            )

    def test_dash_costs_action_for_plain_creature(self) -> None:
        cost = action_cost(Action(name=ActionType.DASH), creature=_plain_creature())
        assert cost.actions == 1
        assert cost.bonus_actions == 0

    def test_dash_costs_action_without_creature(self) -> None:
        """No creature = standard action cost."""
        cost = action_cost(Action(name=ActionType.DASH))
        assert cost.actions == 1

    def test_disengage_costs_action_without_creature(self) -> None:
        cost = action_cost(Action(name=ActionType.DISENGAGE))
        assert cost.actions == 1

    def test_attack_unaffected_by_rogue(self) -> None:
        """Cunning Action only applies to Dash/Disengage."""
        cost = action_cost(Action(name=ActionType.ATTACK, params={"target_id": "x"}), creature=_rogue())
        assert cost.actions == 1
        assert cost.bonus_actions == 0


# ---------------------------------------------------------------------------
# Rogue can Dash + Attack in one turn (bonus + action)
# ---------------------------------------------------------------------------


class TestCunningActionBudget:
    def test_rogue_can_dash_and_attack_same_turn(self) -> None:
        """Rogue: Dash (bonus via cost_mode) + Attack (action) should both be affordable."""
        rogue = _rogue()
        budget = TurnBudget(actions=1, bonus_actions=1, movement_remaining=30)

        dash_cost = action_cost(
            Action(name=ActionType.DASH, params={"cost_mode": "bonus_action"}),
            creature=rogue,
        )
        assert budget.can_afford(dash_cost)
        budget.consume(dash_cost)

        atk_cost = action_cost(Action(name=ActionType.ATTACK, params={"target_id": "x"}), creature=rogue)
        assert budget.can_afford(atk_cost)

    def test_fighter_cannot_dash_and_attack_same_turn(self) -> None:
        """Fighter: Dash (action) + Attack (action) — not enough actions."""
        fighter = _fighter()
        budget = TurnBudget(actions=1, bonus_actions=1, movement_remaining=30)

        dash_cost = action_cost(Action(name=ActionType.DASH), creature=fighter)
        assert budget.can_afford(dash_cost)
        budget.consume(dash_cost)

        atk_cost = action_cost(Action(name=ActionType.ATTACK, params={"target_id": "x"}), creature=fighter)
        assert not budget.can_afford(atk_cost)
