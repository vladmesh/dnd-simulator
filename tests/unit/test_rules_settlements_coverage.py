"""Coverage for stability thresholds in settlement prosperity drift."""

import pytest

from dnd_simulator.rules.settlements import prosperity_drift


@pytest.mark.parametrize(
    ("stability", "expected_drift"),
    [(29.9, -2.0), (30.0, -0.5), (40.0, -0.5), (49.9, -0.5), (50.0, 0.0)],
)
def test_prosperity_drift_stability_thresholds(stability: float, expected_drift: float) -> None:
    assert prosperity_drift(50.0, 50.0, stability) == expected_drift
