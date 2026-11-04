"""Coverage for Paladin progression after choosing a fighting style."""

import pytest
from test_rules_perform_level_up import _paladin_l1

from dnd_simulator.core.class_features import FightingStyle, PaladinFeatures
from dnd_simulator.rules.perform_level_up import perform_level_up


@pytest.mark.parametrize("style", [FightingStyle.DEFENSE, FightingStyle.DUELING])
def test_paladin_l2_to_l3_preserves_fighting_style(style: FightingStyle) -> None:
    character = _paladin_l1()
    perform_level_up(character, fighting_style=style)
    character.level_up_available = True

    result = perform_level_up(character, fighting_style=None)

    assert result is None
    assert character.level == 3
    assert character.level_up_available is False
    assert character.class_features == [PaladinFeatures(level=3, fighting_style=style)]
