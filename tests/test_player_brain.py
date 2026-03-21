"""Tests for PlayerBrain queue-based pattern."""

from __future__ import annotations

import threading

from dnd_simulator.core.action import Action
from dnd_simulator.core.awareness import PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.character import Creature


def _make_creature() -> Creature:
    return Creature(id="test", name="Test", location_id="r1")


def _make_awareness() -> PeacefulAwareness:
    return PeacefulAwareness(
        hour=10,
        day=1,
        month=1,
        year=1,
        weather={"condition": "clear", "temperature": 20},
        location_name="Field",
        region_name="Plains",
        settlements=None,
        territory_owner=None,
        nation_info=None,
    )


class TestPlayerBrainQueue:
    def test_submit_unblocks_choose(self) -> None:
        """submit_action unblocks choose_action in another thread."""
        brain = PlayerBrain()
        result: list[Action] = []

        def choose() -> None:
            action = brain.choose_action(_make_creature(), _make_awareness(), [])
            result.append(action)

        t = threading.Thread(target=choose)
        t.start()

        brain.submit_action(Action(name="idle"))
        t.join(timeout=2)
        assert not t.is_alive()
        assert result == [Action(name="idle")]

    def test_on_turn_fires_before_blocking(self) -> None:
        """on_turn callback fires before choose_action blocks on queue."""
        brain = PlayerBrain()
        turns: list[str] = []

        def on_turn(
            creature: Creature,
            awareness: PeacefulAwareness,
            events: list[PerceivedEvent],
        ) -> None:
            turns.append(creature.id)
            brain.submit_action(Action(name="say", params={"text": "hello"}))

        brain.set_on_turn(on_turn)  # type: ignore[arg-type]

        action = brain.choose_action(_make_creature(), _make_awareness(), [])
        assert action == Action(name="say", params={"text": "hello"})
        assert turns == ["test"]

    def test_no_on_turn_still_works(self) -> None:
        """Without on_turn callback, choose_action just waits on queue."""
        brain = PlayerBrain()

        # Pre-fill queue
        brain.submit_action(Action(name="dodge"))
        action = brain.choose_action(_make_creature(), _make_awareness(), [])
        assert action == Action(name="dodge")

    def test_multiple_actions_queued(self) -> None:
        """Multiple actions can be queued and consumed in order."""
        brain = PlayerBrain()
        brain.submit_action(Action(name="attack", params={"target_id": "g1"}))
        brain.submit_action(Action(name="dodge"))

        a1 = brain.choose_action(_make_creature(), _make_awareness(), [])
        a2 = brain.choose_action(_make_creature(), _make_awareness(), [])
        assert a1.name == "attack"
        assert a2.name == "dodge"
