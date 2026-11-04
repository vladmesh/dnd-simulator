"""Coverage for spring/autumn seasons and southern-hemisphere temperatures."""

import pytest

from dnd_simulator.layers.geography.models import Season
from dnd_simulator.rules.geography import calculate_base_temperature, get_season


@pytest.mark.parametrize(
    ("month", "latitude", "expected"),
    [
        (3, 50.0, Season.SPRING),
        (4, 50.0, Season.SPRING),
        (5, 50.0, Season.SPRING),
        (9, -30.0, Season.SPRING),
        (10, -30.0, Season.SPRING),
        (11, -30.0, Season.SPRING),
        (9, 50.0, Season.AUTUMN),
        (10, 50.0, Season.AUTUMN),
        (11, 50.0, Season.AUTUMN),
        (3, -30.0, Season.AUTUMN),
        (4, -30.0, Season.AUTUMN),
        (5, -30.0, Season.AUTUMN),
    ],
)
def test_spring_and_autumn_in_each_hemisphere(month: int, latitude: float, expected: Season) -> None:
    assert get_season(month, latitude) == expected


@pytest.mark.parametrize(("month", "expected"), [(1, 28.2), (7, 20.2)])
def test_southern_hemisphere_seasonal_temperature(month: int, expected: float) -> None:
    assert calculate_base_temperature(latitude=-30.0, month=month, hour=15, elevation=0.0) == expected
