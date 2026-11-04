"""Validation edge cases of content_loader.schemas content models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dnd_simulator.content_loader.schemas import (
    AbilityScoresContent,
    ActivationTriggerContent,
    BattleMapContent,
    GoalContent,
    InnerSelfContent,
    NpcContent,
)


class TestLocalizedText:
    def test_plain_string_becomes_english_dict(self) -> None:
        npc = NpcContent.model_validate({"name": "Bob"})
        assert npc.name == {"en": "Bob"}

    def test_dict_is_kept(self) -> None:
        npc = NpcContent.model_validate({"name": {"en": "Bob", "ru": "Боб"}})
        assert npc.name == {"en": "Bob", "ru": "Боб"}

    def test_invalid_type_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid localized text"):
            NpcContent.model_validate({"name": 42})


class TestGoalContent:
    def test_typed_goal(self) -> None:
        goal = GoalContent.model_validate({"type": "protect", "target_id": "gate"})
        assert goal.target_id == "gate"

    def test_freeform_goal(self) -> None:
        goal = GoalContent.model_validate({"text": "Find peace"})
        assert goal.text == "Find peace"

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"type": "protect"},
            {"target_id": "gate"},
            {"type": "protect", "target_id": "gate", "text": "both"},
            {"text": ""},
        ],
    )
    def test_ambiguous_or_empty_goal_rejected(self, payload: dict[str, object]) -> None:
        with pytest.raises(ValidationError, match="goal must be typed"):
            GoalContent.model_validate(payload)


class TestInnerSelfContent:
    def test_duplicate_relation_type_for_target_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate relationship type"):
            InnerSelfContent.model_validate(
                {
                    "relations": [
                        {"target_id": "hero", "type": "trusts"},
                        {"target_id": "hero", "type": "trusts", "intensity": 10},
                    ]
                }
            )

    def test_different_types_for_same_target_allowed(self) -> None:
        core = InnerSelfContent.model_validate(
            {"relations": [{"target_id": "hero", "type": "trusts"}, {"target_id": "hero", "type": "fears"}]}
        )
        assert len(core.relations) == 2


class TestAbilityScoresCoercion:
    def test_instance_passes_through(self) -> None:
        scores = AbilityScoresContent.model_validate({"str": 15})
        npc = NpcContent(name={"en": "Bob"}, ability_scores=scores)
        assert npc.ability_scores.str_ == 15

    def test_dict_is_validated(self) -> None:
        npc = NpcContent.model_validate({"name": "Bob", "ability_scores": {"dex": 14}})
        assert npc.ability_scores.dex == 14

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid ability_scores"):
            NpcContent.model_validate({"name": "Bob", "ability_scores": [1, 2, 3]})


class TestBattleMapContent:
    def test_valid_walls(self) -> None:
        bm = BattleMapContent(width=30, height=20, walls=[[0, 0, 30, 20]])
        assert bm.walls == [[0, 0, 30, 20]]

    def test_wall_x_outside_grid_rejected(self) -> None:
        with pytest.raises(ValidationError, match="wall x out of grid"):
            BattleMapContent(width=30, height=20, walls=[[0, 0, 35, 5]])

    def test_wall_y_outside_grid_rejected(self) -> None:
        with pytest.raises(ValidationError, match="wall y out of grid"):
            BattleMapContent(width=30, height=20, walls=[[0, 0, 10, 25]])

    def test_wall_negative_y_rejected(self) -> None:
        with pytest.raises(ValidationError, match="wall y out of grid"):
            BattleMapContent(width=30, height=20, walls=[[0, -5, 10, 5]])


class TestActivationTriggerContent:
    def test_whitespace_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="trigger id must not be empty"):
            ActivationTriggerContent.model_validate(
                {"id": "   ", "on": {"event": "combat_started"}, "until": {"event": "combat_ended"}}
            )


class TestNpcLegacyMemory:
    def test_legacy_memory_key_rejected(self) -> None:
        with pytest.raises(ValidationError, match="inner_self, not memory"):
            NpcContent.model_validate({"name": "Bob", "memory": {"tags": []}})
