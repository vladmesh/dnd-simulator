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


# ---------------------------------------------------------------------------
# ParamDef on DASH / DISENGAGE
# ---------------------------------------------------------------------------


class TestCostModeParamDef:
    def test_dash_has_cost_mode_param(self) -> None:
        """DASH ActionDef declares cost_mode so brains can pass it."""
        from dnd_simulator.core.action_defs import get_action_def

        ad = get_action_def(ActionType.DASH)
        param_names = [p.name for p in ad.params]
        assert "cost_mode" in param_names

    def test_disengage_has_cost_mode_param(self) -> None:
        """DISENGAGE ActionDef declares cost_mode so brains can pass it."""
        from dnd_simulator.core.action_defs import get_action_def

        ad = get_action_def(ActionType.DISENGAGE)
        param_names = [p.name for p in ad.params]
        assert "cost_mode" in param_names

    def test_cost_mode_param_is_optional(self) -> None:
        """cost_mode is not required — non-rogues don't need it."""
        from dnd_simulator.core.action_defs import get_action_def

        ad = get_action_def(ActionType.DASH)
        cost_mode_param = next(p for p in ad.params if p.name == "cost_mode")
        assert not cost_mode_param.required


# ---------------------------------------------------------------------------
# RuleBrain prefers bonus action Dash for rogues
# ---------------------------------------------------------------------------


class TestRuleBrainCunningAction:
    def test_rogue_dashes_as_bonus_action(self) -> None:
        """Rogue RuleBrain should Dash with cost_mode=bonus_action to save the action."""
        from dnd_simulator.core.awareness import CombatAwareness, CombatEntity
        from dnd_simulator.core.brain import RuleBrain

        rogue = _rogue()
        rogue.attacks = ()  # ensure no equipped weapon attack

        awareness = CombatAwareness(
            self_hp=20,
            self_max_hp=20,
            self_ac=14,
            self_speed=30,
            self_weapon="fists",
            self_weapon_damage="1",
            self_x=0,
            self_y=0,
            nearby=[
                CombatEntity(
                    id="enemy",
                    description="Bandit",
                    is_hostile=True,
                    is_wounded=False,
                    distance_ft=60,
                    direction="north",
                    x=0,
                    y=60,
                ),
            ],
            turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=0),
        )
        brain = RuleBrain()
        action = brain.choose_action(rogue, awareness, [])
        assert action.name == ActionType.DASH
        assert action.params["cost_mode"] == "bonus_action"

    def test_fighter_dashes_without_cost_mode(self) -> None:
        """Fighter RuleBrain dashes normally — no cost_mode param."""
        from dnd_simulator.core.awareness import CombatAwareness, CombatEntity
        from dnd_simulator.core.brain import RuleBrain

        fighter = _fighter()

        awareness = CombatAwareness(
            self_hp=30,
            self_max_hp=30,
            self_ac=16,
            self_speed=30,
            self_weapon="fists",
            self_weapon_damage="1",
            self_x=0,
            self_y=0,
            nearby=[
                CombatEntity(
                    id="enemy",
                    description="Bandit",
                    is_hostile=True,
                    is_wounded=False,
                    distance_ft=60,
                    direction="north",
                    x=0,
                    y=60,
                ),
            ],
            turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=0),
        )
        brain = RuleBrain()
        action = brain.choose_action(fighter, awareness, [])
        assert action.name == ActionType.DASH
        assert "cost_mode" not in (action.params or {})
