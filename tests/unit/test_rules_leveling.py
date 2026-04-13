"""Formula tests for ``rules/leveling.py`` (sprint 017 phase 5 task 2).

Pins the XP-by-CR table (DMG p.275) and the level thresholds (PHB p.15),
plus derived helpers ``xp_to_next_level`` and ``can_level_up``.
"""

from __future__ import annotations

import pytest

from dnd_simulator.rules.leveling import (
    MAX_LEVEL,
    can_level_up,
    level_for_xp,
    xp_for_cr,
    xp_to_next_level,
)


class TestXpForCr:
    def test_cr_one_eighth(self) -> None:
        assert xp_for_cr(0.125) == 25

    def test_cr_one(self) -> None:
        assert xp_for_cr(1) == 200

    def test_cr_five(self) -> None:
        assert xp_for_cr(5) == 1800

    def test_cr_ten(self) -> None:
        assert xp_for_cr(10) == 5900

    def test_unknown_cr_raises(self) -> None:
        with pytest.raises(ValueError, match=r"CR 11\.0 not in XP table"):
            xp_for_cr(11.0)


class TestLevelForXp:
    def test_zero_xp_is_level_1(self) -> None:
        assert level_for_xp(0) == 1

    def test_below_l2_threshold(self) -> None:
        assert level_for_xp(299) == 1

    def test_at_l2_threshold(self) -> None:
        assert level_for_xp(300) == 2

    def test_below_l3_threshold(self) -> None:
        assert level_for_xp(899) == 2

    def test_at_l3_threshold(self) -> None:
        assert level_for_xp(900) == 3

    def test_at_max_level_threshold(self) -> None:
        assert level_for_xp(355_000) == MAX_LEVEL

    def test_above_max_level_threshold_caps(self) -> None:
        assert level_for_xp(1_000_000) == MAX_LEVEL


class TestXpToNextLevel:
    def test_fresh_char_needs_300(self) -> None:
        assert xp_to_next_level(0) == 300

    def test_partway_to_l2(self) -> None:
        assert xp_to_next_level(100) == 200

    def test_at_l2_threshold_returns_delta_to_l3(self) -> None:
        # at exactly 300 XP: current level is 2, next is 900
        assert xp_to_next_level(300) == 600

    def test_at_max_level_returns_zero(self) -> None:
        assert xp_to_next_level(355_000) == 0


class TestCanLevelUp:
    def test_l1_below_threshold_cannot(self) -> None:
        assert can_level_up(xp=299, current_level=1) is False

    def test_l1_at_threshold_can(self) -> None:
        assert can_level_up(xp=300, current_level=1) is True

    def test_max_level_cannot(self) -> None:
        assert can_level_up(xp=1_000_000, current_level=MAX_LEVEL) is False

    def test_already_caught_up_cannot(self) -> None:
        # XP only qualifies for level 2 and char is already level 2
        assert can_level_up(xp=300, current_level=2) is False
