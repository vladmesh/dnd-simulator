"""Coverage for the level floor when XP is below every threshold."""

import pytest

from dnd_simulator.rules.leveling import level_for_xp


@pytest.mark.parametrize("xp", [-1, -300, -1_000_000])
def test_negative_xp_returns_level_one(xp: int) -> None:
    assert level_for_xp(xp) == 1
