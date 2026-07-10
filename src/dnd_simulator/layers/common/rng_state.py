"""JSON-safe helpers for ``random.Random`` state."""

from __future__ import annotations

import random
from typing import Any, cast


def _tuples_to_lists(value: object) -> object:
    if isinstance(value, tuple):
        return [_tuples_to_lists(item) for item in value]
    if isinstance(value, list):
        return [_tuples_to_lists(item) for item in value]
    return value


def _lists_to_tuples(value: object) -> object:
    if isinstance(value, list):
        return tuple(_lists_to_tuples(item) for item in value)
    return value


def dump_rng_state(rng: random.Random) -> list[Any]:
    """Return a JSON-compatible snapshot of a ``random.Random`` instance."""
    state = _tuples_to_lists(rng.getstate())
    if not isinstance(state, list):
        raise TypeError("random state did not serialize to a list")
    return state


def load_rng_state(rng: random.Random, state: list[Any]) -> None:
    """Restore a ``random.Random`` instance from ``dump_rng_state`` output."""
    rng.setstate(cast(tuple[Any, ...], _lists_to_tuples(state)))
