"""Brain ABC and player brain for creatures.

Concrete AI implementations live near their dependencies:
- RuleBrain in `dnd_simulator.rules.rule_brain` (consumes rules/*)
- LlmBrain in `dnd_simulator.llm.brain` (consumes llm/*)
"""

from __future__ import annotations

import queue
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from dnd_simulator.core.action import SKIP, Action
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature


# Callback type: notified when it's the player's turn (awareness push).
OnTurnCallback = Callable[
    ["Creature", "PeacefulAwareness | CombatAwareness", "list[PerceivedEvent]"],
    None,
]

# Callback type: notified when a reaction is available for the player.
OnReactionCallback = Callable[
    ["Creature", "ReactionTrigger", "list[ReactionOption]"],
    None,
]


class Brain(ABC):
    """Strategy for choosing actions. Injected into Creature."""

    @abstractmethod
    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        """Decide what to do this turn. Must return a valid Action."""

    def choose_reaction(
        self,
        creature: Creature,
        trigger: ReactionTrigger,
        options: list[ReactionOption],
    ) -> Action:
        """Decide whether to use a reaction. Default: skip.

        Subclasses override for specific reaction logic. Safe default
        means new brain types don't need to implement reactions immediately.
        """
        return SKIP


class PlayerBrain(Brain):
    """Brain controlled by external input via queue + on_turn callback.

    When it's the player's turn, on_turn fires (so transport can send awareness).
    Then choose_action blocks on the queue until transport calls submit_action().
    """

    def __init__(self) -> None:
        self._action_queue: queue.Queue[Action] = queue.Queue()
        self._reaction_queue: queue.Queue[Action] = queue.Queue()
        self._on_turn: OnTurnCallback | None = None
        self._on_reaction: OnReactionCallback | None = None

    def set_on_turn(self, callback: OnTurnCallback) -> None:
        """Transport sets this to receive awareness when it's the player's turn."""
        self._on_turn = callback

    def set_on_reaction(self, callback: OnReactionCallback) -> None:
        """Transport sets this to receive reaction prompts."""
        self._on_reaction = callback

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        if self._on_turn:
            self._on_turn(creature, awareness, events)
        return self._action_queue.get()

    def choose_reaction(
        self,
        creature: Creature,
        trigger: ReactionTrigger,
        options: list[ReactionOption],
    ) -> Action:
        if self._on_reaction is None:
            raise RuntimeError("PlayerBrain.choose_reaction called without on_reaction wired")
        self._on_reaction(creature, trigger, options)
        return self._reaction_queue.get()

    def submit_action(self, action: Action) -> None:
        """Called by transport to provide the player's chosen action."""
        self._action_queue.put(action)

    def submit_reaction(self, action: Action) -> None:
        """Called by transport to provide the player's chosen reaction."""
        self._reaction_queue.put(action)
