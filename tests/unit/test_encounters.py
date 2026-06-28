"""Tests for the pure encounter-roll helper."""

from dnd_simulator.core.models import TimeOfDay
from dnd_simulator.rules.encounters import is_active_at_time


class TestIsActiveAtTime:
    def test_untagged_always_active(self) -> None:
        assert is_active_at_time(None, is_day=True) is True
        assert is_active_at_time(None, is_day=False) is True

    def test_day_tag_active_only_in_daylight(self) -> None:
        assert is_active_at_time(TimeOfDay.DAY, is_day=True) is True
        assert is_active_at_time(TimeOfDay.DAY, is_day=False) is False

    def test_night_tag_active_only_after_dark(self) -> None:
        assert is_active_at_time(TimeOfDay.NIGHT, is_day=False) is True
        assert is_active_at_time(TimeOfDay.NIGHT, is_day=True) is False
