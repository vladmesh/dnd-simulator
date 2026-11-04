"""Tests for invariants of persisted creature intents (core/intent.py)."""

from __future__ import annotations

import pytest

from dnd_simulator.core.intent import IntentType, TimedIntent, TravelIntent
from dnd_simulator.core.resource import RestType


class TestTimedIntent:
    def test_valid_wait_and_sleep(self) -> None:
        wait = TimedIntent(IntentType.WAIT, started_at_seconds=0, wake_at_seconds=60)
        sleep = TimedIntent(IntentType.SLEEP, 10, 10, rest_type=RestType.LONG_REST)
        assert wait.rest_type is None
        assert sleep.rest_type is RestType.LONG_REST

    def test_travel_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="wait or sleep"):
            TimedIntent(IntentType.TRAVEL, 0, 60)

    def test_wake_before_start_rejected(self) -> None:
        with pytest.raises(ValueError, match="wake time"):
            TimedIntent(IntentType.WAIT, 100, 99)

    def test_rest_type_on_wait_rejected(self) -> None:
        with pytest.raises(ValueError, match="rest completion"):
            TimedIntent(IntentType.WAIT, 0, 60, rest_type=RestType.SHORT_REST)


class TestTravelIntent:
    def test_valid_travel(self) -> None:
        intent = TravelIntent(0, "c", ("b", "c"), next_arrival_seconds=30)
        assert intent.kind is IntentType.TRAVEL
        assert intent.fleeing is False

    def test_non_travel_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="travel kind"):
            TravelIntent(0, "c", ("c",), 30, kind=IntentType.WAIT)

    def test_empty_route_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            TravelIntent(0, "c", (), 30)

    def test_destination_not_last_rejected(self) -> None:
        with pytest.raises(ValueError, match="final route node"):
            TravelIntent(0, "c", ("c", "b"), 30)

    def test_arrival_before_start_rejected(self) -> None:
        with pytest.raises(ValueError, match="arrival time"):
            TravelIntent(50, "c", ("c",), 49)
