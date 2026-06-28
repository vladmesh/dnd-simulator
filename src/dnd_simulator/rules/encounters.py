"""Pure encounter-roll helpers."""

from __future__ import annotations

from dnd_simulator.core.models import TimeOfDay


def is_active_at_time(time_of_day: TimeOfDay | None, is_day: bool) -> bool:
    """Whether a time-of-day-tagged spawn may roll right now.

    Untagged spawns are always active; a tagged spawn is active only when its tag
    matches the current phase (DAY when it is day, NIGHT when it is not).
    """
    if time_of_day is None:
        return True
    return (time_of_day is TimeOfDay.DAY) == is_day
