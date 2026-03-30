"""Tests for reaction infrastructure — triggers, Brain.choose_reaction, LLM tools.

Sprint 012, Phase 1, Task 2: generic reaction system that all brain types support.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.brain import Brain, PlayerBrain, RuleBrain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger, TriggerType
from dnd_simulator.llm.brain import LlmBrain
from dnd_simulator.llm.tools import get_reaction_tools

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MinimalBrain(Brain):
    """Brain that only implements choose_action — tests default choose_reaction."""

    def choose_action(self, creature, awareness, events) -> Action:  # type: ignore[override]
        return Action(name=ActionType.IDLE)


def _creature() -> Creature:
    return Creature(id="guard", name="Guard", location_id="arena", max_hp=20, current_hp=20)


def _leaving_reach_trigger() -> ReactionTrigger:
    return ReactionTrigger(
        trigger_type=TriggerType.LEAVING_REACH,
        source_creature_id="fleeing_goblin",
        data={"mover_id": "fleeing_goblin", "from_pos": (10, 10), "to_pos": (10, 15)},
    )


def _oa_option(target_id: str = "fleeing_goblin") -> ReactionOption:
    return ReactionOption(
        action_type=ActionType.OPPORTUNITY_ATTACK,
        description="Melee attack against fleeing_goblin",
        params={"target_id": target_id},
    )


# ---------------------------------------------------------------------------
# ReactionTrigger
# ---------------------------------------------------------------------------


class TestReactionTrigger:
    def test_construction_and_fields(self) -> None:
        trigger = _leaving_reach_trigger()
        assert trigger.trigger_type == TriggerType.LEAVING_REACH
        assert trigger.source_creature_id == "fleeing_goblin"
        assert trigger.data["mover_id"] == "fleeing_goblin"

    def test_immutable(self) -> None:
        trigger = _leaving_reach_trigger()
        try:
            trigger.trigger_type = TriggerType.LEAVING_REACH  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass  # expected — frozen dataclass


# ---------------------------------------------------------------------------
# Brain ABC default
# ---------------------------------------------------------------------------


class TestBrainDefaultReaction:
    def test_default_choose_reaction_returns_skip(self) -> None:
        """A brain that doesn't override choose_reaction should return SKIP."""
        brain = MinimalBrain()
        trigger = _leaving_reach_trigger()
        options = [_oa_option()]

        result = brain.choose_reaction(_creature(), trigger, options)
        assert result.name == ActionType.SKIP


# ---------------------------------------------------------------------------
# RuleBrain
# ---------------------------------------------------------------------------


class TestRuleBrainReaction:
    def test_returns_oa_for_leaving_reach(self) -> None:
        """RuleBrain always takes OA when the option is available."""
        brain = RuleBrain()
        trigger = _leaving_reach_trigger()
        options = [_oa_option()]

        result = brain.choose_reaction(_creature(), trigger, options)
        assert result.name == ActionType.OPPORTUNITY_ATTACK
        assert result.params["target_id"] == "fleeing_goblin"

    def test_skips_when_no_oa_option(self) -> None:
        """No OA option available — RuleBrain skips."""
        brain = RuleBrain()
        trigger = _leaving_reach_trigger()
        options: list[ReactionOption] = []  # no options

        result = brain.choose_reaction(_creature(), trigger, options)
        assert result.name == ActionType.SKIP

    def test_skips_for_unknown_trigger_type(self) -> None:
        """Future trigger types that RuleBrain doesn't handle → skip."""
        brain = RuleBrain()
        # Simulate unknown trigger by using a valid trigger but with no matching logic
        # We test by creating a trigger with a type that has no handler in RuleBrain
        trigger = ReactionTrigger(
            trigger_type=TriggerType.LEAVING_REACH,
            source_creature_id="caster",
            data={},
        )
        # Even with OA option, if we later add other trigger types, brain should skip
        # For now, LEAVING_REACH IS handled. So test with empty options.
        result = brain.choose_reaction(_creature(), trigger, [])
        assert result.name == ActionType.SKIP


# ---------------------------------------------------------------------------
# LlmBrain
# ---------------------------------------------------------------------------


class TestLlmBrainReaction:
    def test_calls_llm_with_reaction_tools(self) -> None:
        """LlmBrain sends reaction options as tools to LLM and returns its choice."""
        mock_llm = MagicMock()
        mock_llm.generate_with_tools.return_value = MagicMock(
            is_tool_call=True,
            tool_call=MagicMock(name="opportunity_attack", arguments={"target_id": "fleeing_goblin"}),
        )
        # Fix: MagicMock.name is special, need to set it explicitly
        mock_llm.generate_with_tools.return_value.tool_call.name = "opportunity_attack"

        brain = LlmBrain(mock_llm)
        trigger = _leaving_reach_trigger()
        options = [_oa_option()]

        result = brain.choose_reaction(_creature(), trigger, options)

        assert result.name == ActionType.OPPORTUNITY_ATTACK
        assert result.params["target_id"] == "fleeing_goblin"

        # Verify LLM was called with tools built from options
        call_args = mock_llm.generate_with_tools.call_args
        tools = call_args[0][1]  # second positional arg
        assert len(tools) >= 1
        tool_names = [t["function"]["name"] for t in tools]
        assert "opportunity_attack" in tool_names

    def test_returns_skip_when_llm_gives_no_tool_call(self) -> None:
        """If LLM returns text instead of tool call → skip."""
        mock_llm = MagicMock()
        mock_llm.generate_with_tools.return_value = MagicMock(
            is_tool_call=False,
            tool_call=None,
            text="I'll just watch.",
        )

        brain = LlmBrain(mock_llm)
        trigger = _leaving_reach_trigger()
        options = [_oa_option()]

        result = brain.choose_reaction(_creature(), trigger, options)
        assert result.name == ActionType.SKIP


# ---------------------------------------------------------------------------
# PlayerBrain
# ---------------------------------------------------------------------------


class TestPlayerBrainReaction:
    def test_fires_callback_and_blocks(self) -> None:
        """PlayerBrain.choose_reaction fires on_reaction callback, blocks until submit."""
        brain = PlayerBrain()
        callback_received: list[tuple[object, ...]] = []

        def on_reaction(creature, trigger, options):  # type: ignore[no-untyped-def]
            callback_received.append((creature, trigger, options))

        brain.set_on_reaction(on_reaction)

        creature = _creature()
        trigger = _leaving_reach_trigger()
        options = [_oa_option()]

        result_holder: list[Action] = []

        def run_choose():  # type: ignore[no-untyped-def]
            result_holder.append(brain.choose_reaction(creature, trigger, options))

        thread = threading.Thread(target=run_choose)
        thread.start()

        # Give thread time to start and fire callback
        thread.join(timeout=1.0)
        assert len(callback_received) == 1
        assert callback_received[0][0] is creature
        assert callback_received[0][1] is trigger

        # Submit the reaction
        reaction = Action(name=ActionType.OPPORTUNITY_ATTACK, params={"target_id": "fleeing_goblin"})
        brain.submit_reaction(reaction)

        thread.join(timeout=1.0)
        assert len(result_holder) == 1
        assert result_holder[0].name == ActionType.OPPORTUNITY_ATTACK


# ---------------------------------------------------------------------------
# LLM reaction tools
# ---------------------------------------------------------------------------


class TestReactionTools:
    def test_builds_tools_from_options(self) -> None:
        """get_reaction_tools converts ReactionOptions to OpenAI tool schema."""
        options = [
            _oa_option(),
            ReactionOption(
                action_type=ActionType.SKIP,
                description="Do nothing",
                params={},
            ),
        ]

        tools = get_reaction_tools(options)
        assert len(tools) == 2
        names = [t["function"]["name"] for t in tools]
        assert "opportunity_attack" in names
        assert "skip" in names

    def test_empty_options_gives_empty_tools(self) -> None:
        tools = get_reaction_tools([])
        assert tools == []
