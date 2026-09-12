"""Typed inner self for persistent creatures.

The model is deliberately pure domain data: rules, content loading, save state,
and LLM prompts can all use it without importing an entities-layer model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from dnd_simulator.core.models import EventType

RELATIONSHIP_INTENSITY_MIN = 1
RELATIONSHIP_INTENSITY_MAX = 100
DEFAULT_RELATIONSHIP_INTENSITY = 50
THOUGHT_BUFFER_CAPACITY = 20
PERCEIVED_EVENT_BUFFER_CAPACITY = 20


class RelationshipType(StrEnum):
    LOVES = "loves"
    HATES = "hates"
    TRUSTS = "trusts"
    FEARS = "fears"
    LOYAL_TO = "loyal_to"


class Mood(StrEnum):
    NEUTRAL = "neutral"
    ANGRY = "angry"
    TIRED = "tired"
    HAPPY = "happy"
    SCARED = "scared"
    GRIEVING = "grieving"
    SUSPICIOUS = "suspicious"
    ALERTED = "alerted"


class GoalType(StrEnum):
    KILL = "kill"
    PROTECT = "protect"
    REACH = "reach"
    OBTAIN = "obtain"
    FLEE = "flee"
    SERVE = "serve"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    ACHIEVED = "achieved"
    FAILED = "failed"


class DigestBoundary(StrEnum):
    """Stable reasons for consuming an inner-self perception buffer."""

    COMBAT_ENDED = "combat_ended"
    DORMANT = "became_dormant"
    INTENT_COMPLETED = "intent_completed"
    INTENT_INTERRUPTED = "intent_interrupted"
    BUFFER_FULL = "buffer_full"


@dataclass(frozen=True)
class BufferedPerceivedEvent:
    """An event retained exactly as one creature perceived it."""

    event_type: EventType
    actor_id: str | None
    target_id: str | None
    description: str
    at_seconds: int


@dataclass(frozen=True)
class Relationship:
    target_id: str
    type: RelationshipType
    intensity: int = DEFAULT_RELATIONSHIP_INTENSITY

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("relationship target_id must not be empty")
        if not RELATIONSHIP_INTENSITY_MIN <= self.intensity <= RELATIONSHIP_INTENSITY_MAX:
            raise ValueError(
                f"relationship intensity must be between {RELATIONSHIP_INTENSITY_MIN} and {RELATIONSHIP_INTENSITY_MAX}"
            )


@dataclass(frozen=True)
class TypedGoal:
    type: GoalType
    target_id: str
    status: GoalStatus = GoalStatus.ACTIVE

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("typed goal target_id must not be empty")


@dataclass(frozen=True)
class FreeformGoal:
    text: str
    status: GoalStatus = GoalStatus.ACTIVE

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("freeform goal text must not be empty")


Goal = TypedGoal | FreeformGoal


@dataclass
class AlignmentAccumulation:
    """Stored alignment evidence.

    Positive ``law_chaos`` pressure points toward chaos and negative pressure
    toward law. Positive ``good_evil`` pressure points toward evil and negative
    pressure toward good. Thresholds, hysteresis, and alignment changes belong
    to the pure digest rules, not this persisted value object.
    """

    law_chaos: int = 0
    good_evil: int = 0


@dataclass
class InnerSelf:
    """Structured core plus the deliberately open personal layer."""

    relations: list[Relationship] = field(default_factory=list)
    mood: Mood = Mood.NEUTRAL
    goals: list[Goal] = field(default_factory=list)
    alignment: AlignmentAccumulation = field(default_factory=AlignmentAccumulation)
    journal: str = ""
    thoughts: list[str] = field(default_factory=list)
    current_conversation: str = ""
    perceived_event_buffer: list[BufferedPerceivedEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        keys = [(relation.target_id, relation.type) for relation in self.relations]
        if len(keys) != len(set(keys)):
            raise ValueError("only one relationship of each type may exist for a target")
        self.thoughts[:] = self.thoughts[-THOUGHT_BUFFER_CAPACITY:]

    def add_thought(self, thought: str) -> None:
        """Append a thought, evicting the oldest entry at fixed capacity."""
        self.thoughts.append(thought)
        if len(self.thoughts) > THOUGHT_BUFFER_CAPACITY:
            del self.thoughts[: len(self.thoughts) - THOUGHT_BUFFER_CAPACITY]

    def relation_targets(self, relation_type: RelationshipType) -> set[str]:
        return {relation.target_id for relation in self.relations if relation.type is relation_type}

    def to_dict(self) -> dict[str, Any]:
        return {
            "relations": [
                {"target_id": relation.target_id, "type": relation.type.value, "intensity": relation.intensity}
                for relation in self.relations
            ],
            "mood": self.mood.value,
            "goals": [
                (
                    {"type": goal.type.value, "target_id": goal.target_id, "status": goal.status.value}
                    if isinstance(goal, TypedGoal)
                    else {"text": goal.text, "status": goal.status.value}
                )
                for goal in self.goals
            ],
            "alignment": {"law_chaos": self.alignment.law_chaos, "good_evil": self.alignment.good_evil},
            "journal": self.journal,
            "thoughts": list(self.thoughts),
            "current_conversation": self.current_conversation,
            "perceived_event_buffer": [
                {
                    "event_type": event.event_type.value,
                    "actor_id": event.actor_id,
                    "target_id": event.target_id,
                    "description": event.description,
                    "at_seconds": event.at_seconds,
                }
                for event in self.perceived_event_buffer
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InnerSelf:
        relations = [
            Relationship(
                target_id=str(item["target_id"]),
                type=RelationshipType(str(item["type"])),
                intensity=int(item.get("intensity", DEFAULT_RELATIONSHIP_INTENSITY)),
            )
            for item in data.get("relations", [])
        ]
        goals: list[Goal] = []
        for item in data.get("goals", []):
            if item.get("type") is not None:
                goals.append(
                    TypedGoal(
                        type=GoalType(str(item["type"])),
                        target_id=str(item["target_id"]),
                        status=GoalStatus(str(item.get("status", GoalStatus.ACTIVE))),
                    )
                )
            else:
                goals.append(
                    FreeformGoal(text=str(item["text"]), status=GoalStatus(str(item.get("status", GoalStatus.ACTIVE))))
                )
        alignment = data.get("alignment", {})
        return cls(
            relations=relations,
            mood=Mood(str(data.get("mood", Mood.NEUTRAL))),
            goals=goals,
            alignment=AlignmentAccumulation(
                law_chaos=int(alignment.get("law_chaos", 0)), good_evil=int(alignment.get("good_evil", 0))
            ),
            journal=str(data.get("journal", "")),
            thoughts=[str(thought) for thought in data.get("thoughts", [])],
            current_conversation=str(data.get("current_conversation", "")),
            perceived_event_buffer=[
                BufferedPerceivedEvent(
                    event_type=EventType(str(event["event_type"])),
                    actor_id=str(event["actor_id"]) if event.get("actor_id") is not None else None,
                    target_id=str(event["target_id"]) if event.get("target_id") is not None else None,
                    description=str(event["description"]),
                    at_seconds=int(event["at_seconds"]),
                )
                for event in data.get("perceived_event_buffer", [])
            ],
        )
