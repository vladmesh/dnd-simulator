"""Pin the in-place contract of ``perform_level_up`` (sprint 017 phase 5 task 1).

``rules/perform_level_up.py`` is an explicit exception to the rules/ purity rule:
it mutates the passed ``Character`` instance rather than returning a new one.
These tests ensure a future refactor does not silently break callers that rely
on identity.
"""

from __future__ import annotations

import pytest

from dnd_simulator.core.character import (
    AbilityScores,
    Character,
    CharClass,
    Race,
)
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle
from dnd_simulator.rules.perform_level_up import perform_level_up


def _fighter_l1_ready_to_level() -> Character:
    return Character(
        id="f",
        name="F",
        location_id="loc",
        max_hp=12,
        current_hp=12,
        ac=10,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=1,
        ability_scores=AbilityScores(),
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE, level=1)],
        level_up_available=True,
    )


class TestPerformLevelUpInPlaceContract:
    def test_returns_none_and_mutates_same_instance(self) -> None:
        c = _fighter_l1_ready_to_level()
        result = perform_level_up(c, fighting_style=None)
        assert result is None
        assert c.level == 2

    def test_clears_level_up_available_flag(self) -> None:
        c = _fighter_l1_ready_to_level()
        perform_level_up(c, fighting_style=None)
        assert c.level_up_available is False

    def test_second_call_without_flag_reset_raises(self) -> None:
        c = _fighter_l1_ready_to_level()
        perform_level_up(c, fighting_style=None)
        with pytest.raises(ValueError, match="No level-up available"):
            perform_level_up(c, fighting_style=None)
