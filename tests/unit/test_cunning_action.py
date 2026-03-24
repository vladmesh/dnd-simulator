"""Tests for Cunning Action — Rogue Dash/Disengage as bonus action."""

from __future__ import annotations

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
from dnd_simulator.rules.actions import action_cost


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
# action_cost with creature
# ---------------------------------------------------------------------------


class TestCunningActionCost:
    def test_dash_costs_bonus_for_rogue(self) -> None:
        cost = action_cost(Action(name=ActionType.DASH), creature=_rogue())
        assert cost.bonus_actions == 1
        assert cost.actions == 0

    def test_disengage_costs_bonus_for_rogue(self) -> None:
        cost = action_cost(Action(name=ActionType.DISENGAGE), creature=_rogue())
        assert cost.bonus_actions == 1
        assert cost.actions == 0

    def test_dash_costs_action_for_fighter(self) -> None:
        cost = action_cost(Action(name=ActionType.DASH), creature=_fighter())
        assert cost.actions == 1
        assert cost.bonus_actions == 0

    def test_disengage_costs_action_for_fighter(self) -> None:
        cost = action_cost(Action(name=ActionType.DISENGAGE), creature=_fighter())
        assert cost.actions == 1
        assert cost.bonus_actions == 0

    def test_dash_costs_action_for_plain_creature(self) -> None:
        cost = action_cost(Action(name=ActionType.DASH), creature=_plain_creature())
        assert cost.actions == 1
        assert cost.bonus_actions == 0

    def test_dash_costs_action_without_creature(self) -> None:
        """Backwards compat: no creature = standard action."""
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
        """Rogue: Dash (bonus) + Attack (action) should both be affordable."""
        rogue = _rogue()
        budget = TurnBudget(actions=1, bonus_actions=1, movement_remaining=30)

        dash_cost = action_cost(Action(name=ActionType.DASH), creature=rogue)
        assert budget.can_afford(dash_cost)
        budget.consume(dash_cost)

        attack_cost = action_cost(Action(name=ActionType.ATTACK, params={"target_id": "x"}), creature=rogue)
        assert budget.can_afford(attack_cost)

    def test_fighter_cannot_dash_and_attack_same_turn(self) -> None:
        """Fighter: Dash (action) + Attack (action) — not enough actions."""
        fighter = _fighter()
        budget = TurnBudget(actions=1, bonus_actions=1, movement_remaining=30)

        dash_cost = action_cost(Action(name=ActionType.DASH), creature=fighter)
        assert budget.can_afford(dash_cost)
        budget.consume(dash_cost)

        attack_cost = action_cost(Action(name=ActionType.ATTACK, params={"target_id": "x"}), creature=fighter)
        assert not budget.can_afford(attack_cost)
