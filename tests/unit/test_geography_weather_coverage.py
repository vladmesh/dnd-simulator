"""Coverage for zero-total normalization and autumn weather modifiers."""

import pytest

from dnd_simulator.layers.geography.models import Season, WeatherCondition
from dnd_simulator.layers.geography.weather import _apply_season_modifiers, _normalize


@pytest.mark.parametrize(
    "probs",
    [
        {},
        {WeatherCondition.CLOUDY: 0.0, WeatherCondition.LIGHT_RAIN: 0.0},
    ],
    ids=["empty", "all-zero"],
)
def test_normalize_zero_total_defaults_to_clear(probs: dict[WeatherCondition, float]) -> None:
    original = dict(probs)

    assert _normalize(probs) == {WeatherCondition.CLEAR: 1.0}
    assert probs == original


@pytest.mark.parametrize(
    ("probs", "expected"),
    [
        (
            {
                WeatherCondition.CLEAR: 0.3,
                WeatherCondition.CLOUDY: 0.3,
                WeatherCondition.LIGHT_RAIN: 0.2,
                WeatherCondition.FOG: 0.1,
                WeatherCondition.SNOW: 0.1,
            },
            {
                WeatherCondition.CLEAR: 0.3,
                WeatherCondition.CLOUDY: 0.36,
                WeatherCondition.LIGHT_RAIN: 0.28,
                WeatherCondition.FOG: 0.13,
                WeatherCondition.SNOW: 0.1,
            },
        ),
        (
            {},
            {
                WeatherCondition.LIGHT_RAIN: 0.0,
                WeatherCondition.FOG: 0.0,
                WeatherCondition.CLOUDY: 0.0,
            },
        ),
    ],
    ids=["existing-weights", "missing-weights"],
)
def test_autumn_boosts_rain_fog_and_clouds_without_mutating_input(
    probs: dict[WeatherCondition, float], expected: dict[WeatherCondition, float]
) -> None:
    original = dict(probs)

    result = _apply_season_modifiers(probs, Season.AUTUMN)

    assert result == pytest.approx(expected)
    assert probs == original
