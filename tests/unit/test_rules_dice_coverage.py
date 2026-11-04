"""Coverage for shared RNG access and invalid die sizes."""

import random

import pytest

from dnd_simulator.rules.dice import get_global_rng, roll, roll_d20


def test_global_rng_controls_default_rolls() -> None:
    rng = get_global_rng()
    original_state = rng.getstate()
    try:
        rng.seed(42)
        expected_rng = random.Random(42)

        assert roll("2d6+3").total == sum(expected_rng.randint(1, 6) for _ in range(2)) + 3
        assert roll_d20().natural == expected_rng.randint(1, 20)
        assert rng.getstate() == expected_rng.getstate()
    finally:
        rng.setstate(original_state)


@pytest.mark.parametrize("expression", ["1d0", "0d0", "2d0+3"])
def test_zero_sided_dice_are_rejected(expression: str) -> None:
    rng = random.Random(42)
    original_state = rng.getstate()

    with pytest.raises(ValueError, match=r"^Invalid dice expression:"):
        roll(expression, rng=rng)

    assert rng.getstate() == original_state
