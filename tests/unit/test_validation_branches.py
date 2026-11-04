"""Branch coverage for individual validation checks not exercised elsewhere."""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Character, CharClass, Creature, Entity
from dnd_simulator.core.class_features import RogueFeatures
from dnd_simulator.core.container import Container
from dnd_simulator.rules.actions import collect_cost_overrides
from dnd_simulator.rules.validation import (
    ActionContext,
    check_cost_mode,
    check_lootable_target,
    check_required_params,
    check_target_not_full_hp,
    check_target_scope,
)

_PEACEFUL = ActionContext(is_combat=False, current_turn_entity_id="actor")


def _actor(**overrides: object) -> Creature:
    fields: dict[str, object] = {"id": "actor", "name": "Actor", "location_id": "loc"}
    fields.update(overrides)
    return Creature(**fields)  # type: ignore[arg-type]


def _ctx(*entities: Entity) -> ActionContext:
    by_id = {e.id: e for e in entities}
    return ActionContext(is_combat=False, current_turn_entity_id="actor", get_entity=by_id.get)


class TestRequiredParams:
    def test_missing_required_param_rejected(self) -> None:
        action = Action(name=ActionType.ATTACK, params={"description": "swing"})
        error = check_required_params(_actor(), action, _PEACEFUL)
        assert error is not None
        assert error.code == "MISSING_REQUIRED_PARAM"
        assert "target_id" in error.message


class TestCostMode:
    def test_unknown_cost_mode_rejected(self) -> None:
        action = Action(name=ActionType.DASH, params={"cost_mode": "bonus_action"})
        error = check_cost_mode(_actor(), action, _PEACEFUL)
        assert error is not None
        assert error.code == "INVALID_COST_MODE"

    def test_matching_cost_override_accepted(self) -> None:
        rogue = Character(
            id="actor",
            name="Rogue",
            location_id="loc",
            char_class=CharClass.ROGUE,
            level=2,
            class_features=[RogueFeatures()],
        )
        override = collect_cost_overrides(rogue)[0]
        action = Action(name=override.action_type, params={"cost_mode": override.cost_type.value})
        assert check_cost_mode(rogue, action, _PEACEFUL) is None


class TestLootableTarget:
    def test_without_entity_lookup_is_skipped(self) -> None:
        action = Action(name=ActionType.TAKE, params={"target_id": "chest"})
        assert check_lootable_target(_actor(), action, _PEACEFUL) is None

    def test_target_in_other_location_rejected(self) -> None:
        chest = Container(id="chest", name="Chest", location_id="elsewhere", gold=3)
        action = Action(name=ActionType.TAKE, params={"target_id": "chest"})
        error = check_lootable_target(_actor(), action, _ctx(chest))
        assert error is not None
        assert error.code == "TARGET_WRONG_LOCATION"

    def test_missing_target_rejected(self) -> None:
        action = Action(name=ActionType.TAKE, params={"target_id": "ghost"})
        error = check_lootable_target(_actor(), action, _ctx())
        assert error is not None
        assert error.code == "TARGET_NOT_FOUND"


class TestLayOnHandsFullHp:
    def test_non_lay_on_hands_ignored(self) -> None:
        assert check_target_not_full_hp(_actor(), Action(name=ActionType.DODGE, params={"x": 1}), _PEACEFUL) is None

    def test_probe_ignored(self) -> None:
        assert check_target_not_full_hp(_actor(), Action(name=ActionType.LAY_ON_HANDS), _PEACEFUL) is None

    def test_self_at_full_hp_rejected(self) -> None:
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 5})
        error = check_target_not_full_hp(_actor(max_hp=10, current_hp=10), action, _PEACEFUL)
        assert error is not None
        assert error.code == "TARGET_FULL_HP"

    def test_wounded_target_accepted(self) -> None:
        ally = _actor(id="ally", max_hp=10, current_hp=3)
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 5, "target_id": "ally"})
        assert check_target_not_full_hp(_actor(), action, _ctx(ally)) is None

    def test_non_creature_target_left_to_other_checks(self) -> None:
        chest = Container(id="chest", name="Chest", location_id="loc")
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 5, "target_id": "chest"})
        assert check_target_not_full_hp(_actor(), action, _ctx(chest)) is None


class TestTargetScope:
    def test_hostile_action_cannot_target_self(self) -> None:
        action = Action(name=ActionType.ATTACK, params={"target_id": "actor"})
        error = check_target_scope(_actor(), action, _PEACEFUL)
        assert error is not None
        assert error.code == "WRONG_TARGET_SCOPE"

    def test_ally_action_may_target_self(self) -> None:
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 1, "target_id": "actor"})
        assert check_target_scope(_actor(), action, _PEACEFUL) is None

    def test_non_creature_target_left_to_target_check(self) -> None:
        chest = Container(id="chest", name="Chest", location_id="loc")
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 1, "target_id": "chest"})
        assert check_target_scope(_actor(), action, _ctx(chest)) is None

    def test_unknown_faction_relation_lets_ally_action_through(self) -> None:
        stranger = _actor(id="stranger")
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 1, "target_id": "stranger"})
        assert check_target_scope(_actor(faction_id="guild"), action, _ctx(stranger)) is None

    def test_ally_action_on_other_faction_rejected(self) -> None:
        stranger = _actor(id="stranger", faction_id="bandits")
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 1, "target_id": "stranger"})
        error = check_target_scope(_actor(faction_id="guild"), action, _ctx(stranger))
        assert error is not None
        assert error.code == "WRONG_TARGET_SCOPE"
