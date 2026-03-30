"""Reaction system types — triggers, options, and data objects.

Generic infrastructure for D&D 5e reactions. Specific reaction types
(opportunity attacks, counterspell, etc.) use these building blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from dnd_simulator.core.action import ActionType


class TriggerType(StrEnum):
    """What event can trigger a reaction."""

    LEAVING_REACH = "leaving_reach"  # creature moves out of melee reach


@dataclass(frozen=True)
class ReactionTrigger:
    """Describes the event that triggered a potential reaction.

    Built by the game loop (Round) when a trigger condition is detected.
    Passed to Brain.choose_reaction so the brain can decide what to do.
    """

    trigger_type: TriggerType
    source_creature_id: str  # who caused the trigger (e.g. the mover)
    data: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ReactionOption:
    """One available reaction a creature can take.

    Pre-built by the caller (Round), not by the brain. The brain picks
    from the list or returns SKIP.
    """

    action_type: ActionType
    description: str
    params: dict[str, object] = field(default_factory=dict)
