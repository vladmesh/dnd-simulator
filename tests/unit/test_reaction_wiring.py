"""Tests for WS reaction wiring: PlayerBrain → GameSession → transport."""

from __future__ import annotations

import threading

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.character import Character, Creature, Race
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger, TriggerType
from dnd_simulator.i18n import set_language


def _make_creature(creature_id: str = "player") -> Creature:
    return Character(id=creature_id, name="Hero", location_id="r1", race=Race.HUMAN)


def _make_trigger() -> ReactionTrigger:
    return ReactionTrigger(
        trigger_type=TriggerType.LEAVING_REACH,
        source_creature_id="goblin_1",
        data={"mover_id": "goblin_1", "from_pos": (5, 5), "to_pos": (6, 5)},
    )


def _make_options() -> list[ReactionOption]:
    return [
        ReactionOption(
            action_type=ActionType.OPPORTUNITY_ATTACK,
            description="Melee attack against goblin_1",
            params={"target_id": "goblin_1"},
        ),
    ]


class TestPlayerBrainReaction:
    """PlayerBrain.choose_reaction with _on_reaction wired blocks on queue."""

    def test_choose_reaction_fires_callback_and_blocks(self) -> None:
        """When _on_reaction is wired, choose_reaction fires it then blocks until submit."""
        brain = PlayerBrain()
        callback_calls: list[tuple[Creature, ReactionTrigger, list[ReactionOption]]] = []

        def on_reaction(creature: Creature, trigger: ReactionTrigger, options: list[ReactionOption]) -> None:
            callback_calls.append((creature, trigger, options))

        brain.set_on_reaction(on_reaction)
        creature = _make_creature()
        trigger = _make_trigger()
        options = _make_options()

        # Run choose_reaction in a thread (it blocks)
        result_holder: list[Action] = []

        def run() -> None:
            result_holder.append(brain.choose_reaction(creature, trigger, options))

        t = threading.Thread(target=run, daemon=True)
        t.start()

        # Wait a bit for the callback to fire
        t.join(timeout=1.0)
        assert len(callback_calls) == 1
        assert callback_calls[0][1].trigger_type == TriggerType.LEAVING_REACH

        # Submit reaction — unblocks choose_reaction
        brain.submit_reaction(Action(name=ActionType.OPPORTUNITY_ATTACK, params={"target_id": "goblin_1"}))
        t.join(timeout=1.0)
        assert not t.is_alive()
        assert result_holder[0].name == ActionType.OPPORTUNITY_ATTACK

    def test_choose_reaction_without_callback_raises(self) -> None:
        """Without _on_reaction wired, choose_reaction must NOT auto-skip — it should raise."""
        brain = PlayerBrain()
        creature = _make_creature()
        trigger = _make_trigger()
        options = _make_options()

        # With no callback wired, PlayerBrain should raise (no silent fallback)
        import pytest

        with pytest.raises(RuntimeError):
            brain.choose_reaction(creature, trigger, options)

    def test_submit_reaction_without_pending_prompt_is_refused(self) -> None:
        """A stray answer (no prompt pending) is dropped, never queued for a later prompt."""
        brain = PlayerBrain()
        assert brain.submit_reaction(Action(name=ActionType.OPPORTUNITY_ATTACK)) is False
        assert brain._reaction_queue.empty()

    def test_stray_answer_does_not_answer_the_next_prompt(self) -> None:
        """Regression: a reaction sent before the prompt used to auto-answer it."""
        brain = PlayerBrain()
        prompted = threading.Event()
        brain.set_on_reaction(lambda creature, trigger, options: prompted.set())
        brain.submit_reaction(Action(name=ActionType.OPPORTUNITY_ATTACK, params={"target_id": "goblin_1"}))

        result: list[Action] = []
        thread = threading.Thread(
            target=lambda: result.append(brain.choose_reaction(_make_creature(), _make_trigger(), _make_options())),
            daemon=True,
        )
        thread.start()
        assert prompted.wait(timeout=1.0)
        thread.join(timeout=0.2)
        assert thread.is_alive(), "the prompt must wait for an answer given after it"

        assert brain.submit_reaction(Action(name=ActionType.SKIP)) is True
        thread.join(timeout=1.0)
        assert result == [Action(name=ActionType.SKIP)]

    def test_only_one_answer_per_prompt(self) -> None:
        """A duplicate answer (double click) is refused, so it cannot answer the next prompt."""
        brain = PlayerBrain()
        prompted = threading.Event()
        brain.set_on_reaction(lambda creature, trigger, options: prompted.set())
        thread = threading.Thread(
            target=brain.choose_reaction, args=(_make_creature(), _make_trigger(), _make_options()), daemon=True
        )
        thread.start()
        assert prompted.wait(timeout=1.0)

        assert brain.submit_reaction(Action(name=ActionType.SKIP)) is True
        assert brain.submit_reaction(Action(name=ActionType.SKIP)) is False
        thread.join(timeout=1.0)
        assert not thread.is_alive()
        assert brain._reaction_queue.empty()

    def test_close_skips_pending_prompt(self) -> None:
        brain = PlayerBrain()
        prompted = threading.Event()
        brain.set_on_reaction(lambda creature, trigger, options: prompted.set())
        result: list[Action] = []
        thread = threading.Thread(
            target=lambda: result.append(brain.choose_reaction(_make_creature(), _make_trigger(), _make_options())),
            daemon=True,
        )
        thread.start()
        assert prompted.wait(timeout=1.0)

        brain.close()
        thread.join(timeout=1.0)
        assert result == [Action(name=ActionType.SKIP)]

    def test_close_declines_later_prompts_without_blocking(self) -> None:
        """A stop that lands before the prompt must not leave the round thread blocked."""
        brain = PlayerBrain()
        calls: list[object] = []
        brain.set_on_reaction(lambda creature, trigger, options: calls.append(trigger))
        brain.close()

        assert brain.choose_reaction(_make_creature(), _make_trigger(), _make_options()) == Action(name=ActionType.SKIP)
        assert calls == []


class TestSessionReactionWiring:
    """GameSession wires on_reaction and exposes submit_player_reaction."""

    def test_session_has_submit_player_reaction(self) -> None:
        """GameSession must have a submit_player_reaction method."""
        from dnd_simulator.service.session import GameSession

        assert hasattr(GameSession, "submit_player_reaction")

    def test_listener_protocol_has_on_reaction(self) -> None:
        """SessionEventListener protocol must include on_reaction."""
        from dnd_simulator.service.session import SessionEventListener

        assert hasattr(SessionEventListener, "on_reaction")


class TestReactionPromptMessage:
    """The reaction_prompt WS message has correct structure."""

    def teardown_method(self) -> None:
        set_language("en")

    def test_reaction_prompt_structure(self) -> None:
        """on_reaction callback builds a message with type, trigger, and options."""
        from dnd_simulator.service.transport_payloads import reaction_to_dict

        trigger = _make_trigger()
        options = _make_options()
        msg = reaction_to_dict(trigger, options)

        assert msg["type"] == "reaction_prompt"
        assert msg["trigger"]["trigger_type"] == "leaving_reach"
        assert msg["trigger"]["source_creature_id"] == "goblin_1"
        assert len(msg["options"]) == 1
        assert msg["options"][0]["action_type"] == "opportunity_attack"
        assert msg["options"][0]["description"] == "Melee attack against goblin_1"
        assert msg["options"][0]["params"]["target_id"] == "goblin_1"

    def test_transport_preserves_prebuilt_description(self) -> None:
        """Transport serializes descriptions and does not try to translate interpolated text."""
        from dnd_simulator.service.transport_payloads import reaction_to_dict

        set_language("ru")
        msg = reaction_to_dict(_make_trigger(), _make_options())

        assert msg["options"][0]["description"] == "Melee attack against goblin_1"
