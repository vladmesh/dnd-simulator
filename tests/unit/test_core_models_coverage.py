"""Coverage for core model time conversions."""

from __future__ import annotations

import pytest

from dnd_simulator.core.models import TimeDelta


@pytest.mark.parametrize(
    ("seconds", "expected_rounds"),
    [(0, 0), (5, 0), (6, 1), (7, 1), (11, 1), (12, 2), (65, 10)],
)
def test_time_delta_rounds_counts_only_complete_rounds(seconds: int, expected_rounds: int) -> None:
    duration = TimeDelta(seconds=seconds)

    assert duration.rounds == expected_rounds
