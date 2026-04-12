import pytest

from dnd_simulator.rules.leveling import (
    MAX_LEVEL,
    can_level_up,
    level_for_xp,
    xp_for_cr,
    xp_to_next_level,
)


class TestXpForCr:
    def test_cr_zero(self) -> None:
        assert xp_for_cr(0) == 10

    def test_fractional_crs(self) -> None:
        assert xp_for_cr(0.125) == 25
        assert xp_for_cr(0.25) == 50
        assert xp_for_cr(0.5) == 100

    def test_integer_crs(self) -> None:
        assert xp_for_cr(1) == 200
        assert xp_for_cr(5) == 1800

    def test_cr_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            xp_for_cr(-1)

    def test_cr_out_of_table_raises(self) -> None:
        with pytest.raises(ValueError):
            xp_for_cr(50)


class TestLevelForXp:
    def test_below_first_threshold(self) -> None:
        assert level_for_xp(0) == 1
        assert level_for_xp(299) == 1

    def test_exact_thresholds(self) -> None:
        assert level_for_xp(300) == 2
        assert level_for_xp(900) == 3

    def test_between_thresholds(self) -> None:
        assert level_for_xp(899) == 2

    def test_past_max_level_caps(self) -> None:
        assert level_for_xp(10_000_000) == MAX_LEVEL


class TestXpToNextLevel:
    def test_from_zero(self) -> None:
        assert xp_to_next_level(0) == 300

    def test_partial_progress(self) -> None:
        assert xp_to_next_level(250) == 50

    def test_exactly_at_level_2(self) -> None:
        assert xp_to_next_level(300) == 600

    def test_at_max_level(self) -> None:
        assert xp_to_next_level(355_000) == 0
        assert xp_to_next_level(10_000_000) == 0


class TestCanLevelUp:
    def test_not_enough_xp(self) -> None:
        assert can_level_up(250, 1) is False

    def test_exactly_enough(self) -> None:
        assert can_level_up(300, 1) is True

    def test_much_more_than_enough(self) -> None:
        assert can_level_up(1000, 1) is True

    def test_max_level_cannot_level(self) -> None:
        assert can_level_up(10_000_000, MAX_LEVEL) is False
