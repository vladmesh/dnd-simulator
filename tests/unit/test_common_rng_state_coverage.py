"""Coverage for recursive RNG-state conversion and JSON persistence."""

import json
import random

import pytest

from dnd_simulator.layers.common.rng_state import _tuples_to_lists, dump_rng_state, load_rng_state


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([], []),
        ([1, (2, [3, (4,)])], [1, [2, [3, [4]]]]),
        (([None, (1.5,)],), [[None, [1.5]]]),
    ],
)
def test_tuples_to_lists_recurses_through_lists(value: object, expected: object) -> None:
    assert _tuples_to_lists(value) == expected


@pytest.mark.parametrize("cached_gaussian", [False, True])
def test_rng_state_json_round_trip_preserves_sequence(cached_gaussian: bool) -> None:
    source = random.Random(42)
    source.random()
    if cached_gaussian:
        source.gauss(0, 1)
    original_state = source.getstate()

    snapshot = dump_rng_state(source)
    assert isinstance(snapshot, list)
    assert isinstance(snapshot[1], list)
    assert source.getstate() == original_state

    restored = random.Random(99)
    load_rng_state(restored, json.loads(json.dumps(snapshot)))

    assert restored.getstate() == original_state
    assert [restored.random() for _ in range(10)] == [source.random() for _ in range(10)]
    assert [restored.gauss(0, 1) for _ in range(4)] == [source.gauss(0, 1) for _ in range(4)]
    assert restored.getstate() == source.getstate()
