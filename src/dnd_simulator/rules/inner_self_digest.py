"""Deterministic inner-self digestion rules.

The rules consume perceived events in their buffered order.  An attack against
the core bearer creates or strengthens ``hates`` and proposes ``angry``; the
death of an ally proposes ``grieving``.  Death completes active ``kill`` goals
and fails active ``protect`` goals.  A core bearer's own attack on an ally adds
one step each toward chaos and evil.  Alignment accumulation is evidence only:
this module never changes a creature's D&D alignment.

When several moods are evidenced, ``MOOD_PRIORITY`` chooses the highest one,
so grieving wins over angry regardless of event order.
"""

from __future__ import annotations

from dataclasses import dataclass

from dnd_simulator.core.inner_self import (
    DEFAULT_RELATIONSHIP_INTENSITY,
    RELATIONSHIP_INTENSITY_MAX,
    AlignmentAccumulation,
    BufferedPerceivedEvent,
    GoalStatus,
    GoalType,
    InnerSelf,
    Mood,
    Relationship,
    RelationshipType,
    TypedGoal,
)
from dnd_simulator.core.models import EventType

HATE_INTENSITY_STEP = 10
ALIGNMENT_EVIDENCE_STEP = 1
MOOD_PRIORITY: dict[Mood, int] = {Mood.ANGRY: 1, Mood.GRIEVING: 2}


@dataclass(frozen=True)
class DigestContext:
    """Simple caller-provided data which identifies the core bearer and allies."""

    self_id: str
    allied_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class GoalStatusChange:
    """The new status for matching active typed goals."""

    type: GoalType
    target_id: str
    status: GoalStatus


@dataclass(frozen=True)
class InnerSelfDigestDelta:
    """Pure changes derived from one ordered batch of perceived events."""

    relationship_updates: tuple[Relationship, ...] = ()
    mood: Mood | None = None
    goal_status_changes: tuple[GoalStatusChange, ...] = ()
    law_chaos_delta: int = 0
    good_evil_delta: int = 0


def derive_delta(core: InnerSelf, events: list[BufferedPerceivedEvent], context: DigestContext) -> InnerSelfDigestDelta:
    """Derive an immutable delta without mutating *core* or its event buffer."""
    allied_ids = _allied_ids(core, context)
    relationships = {(relation.target_id, relation.type): relation for relation in core.relations}
    updates: dict[tuple[str, RelationshipType], Relationship] = {}
    goal_changes: dict[tuple[GoalType, str], GoalStatusChange] = {}
    candidate_moods: set[Mood] = set()
    law_chaos_delta = 0
    good_evil_delta = 0

    for event in events:
        if event.event_type in {EventType.ENTITY_ATTACK, EventType.OPPORTUNITY_ATTACK}:
            actor_id = event.actor_id
            if event.target_id == context.self_id and isinstance(actor_id, str) and actor_id != context.self_id:
                key = (actor_id, RelationshipType.HATES)
                relation = updates.get(key) or relationships.get(key)
                if relation is None:
                    updates[key] = Relationship(actor_id, RelationshipType.HATES, DEFAULT_RELATIONSHIP_INTENSITY)
                else:
                    updates[key] = Relationship(
                        actor_id,
                        RelationshipType.HATES,
                        min(RELATIONSHIP_INTENSITY_MAX, relation.intensity + HATE_INTENSITY_STEP),
                    )
                candidate_moods.add(Mood.ANGRY)

            if event.actor_id == context.self_id and event.target_id in allied_ids:
                law_chaos_delta += ALIGNMENT_EVIDENCE_STEP
                good_evil_delta += ALIGNMENT_EVIDENCE_STEP

        if event.event_type is EventType.ENTITY_DIED and event.target_id is not None:
            if event.target_id in allied_ids:
                candidate_moods.add(Mood.GRIEVING)
            for goal in core.goals:
                if not isinstance(goal, TypedGoal) or goal.status is not GoalStatus.ACTIVE:
                    continue
                if goal.target_id != event.target_id:
                    continue
                if goal.type is GoalType.KILL:
                    goal_changes[(goal.type, goal.target_id)] = GoalStatusChange(
                        goal.type, goal.target_id, GoalStatus.ACHIEVED
                    )
                elif goal.type is GoalType.PROTECT:
                    goal_changes[(goal.type, goal.target_id)] = GoalStatusChange(
                        goal.type, goal.target_id, GoalStatus.FAILED
                    )

    mood = max(candidate_moods, key=lambda candidate: MOOD_PRIORITY[candidate]) if candidate_moods else None
    return InnerSelfDigestDelta(
        relationship_updates=tuple(updates.values()),
        mood=mood,
        goal_status_changes=tuple(goal_changes.values()),
        law_chaos_delta=law_chaos_delta,
        good_evil_delta=good_evil_delta,
    )


def apply_delta(core: InnerSelf, delta: InnerSelfDigestDelta) -> InnerSelf:
    """Return a new inner self with *delta* applied, without mutating *core*."""
    relationship_updates = {(relation.target_id, relation.type): relation for relation in delta.relationship_updates}
    relations = [relationship_updates.pop((relation.target_id, relation.type), relation) for relation in core.relations]
    relations.extend(relationship_updates.values())
    goal_changes = {(change.type, change.target_id): change.status for change in delta.goal_status_changes}
    goals = [
        (
            TypedGoal(goal.type, goal.target_id, goal_changes[(goal.type, goal.target_id)])
            if isinstance(goal, TypedGoal)
            and goal.status is GoalStatus.ACTIVE
            and (goal.type, goal.target_id) in goal_changes
            else goal
        )
        for goal in core.goals
    ]
    return InnerSelf(
        relations=relations,
        mood=delta.mood or core.mood,
        goals=goals,
        alignment=AlignmentAccumulation(
            law_chaos=core.alignment.law_chaos + delta.law_chaos_delta,
            good_evil=core.alignment.good_evil + delta.good_evil_delta,
        ),
        journal=core.journal,
        thoughts=list(core.thoughts),
        current_conversation=core.current_conversation,
        perceived_event_buffer=list(core.perceived_event_buffer),
    )


def _allied_ids(core: InnerSelf, context: DigestContext) -> frozenset[str]:
    relationship_allies = {
        relation.target_id
        for relation in core.relations
        if relation.type in {RelationshipType.LOVES, RelationshipType.TRUSTS, RelationshipType.LOYAL_TO}
    }
    protected_ids = {
        goal.target_id
        for goal in core.goals
        if isinstance(goal, TypedGoal) and goal.type is GoalType.PROTECT and goal.status is GoalStatus.ACTIVE
    }
    return context.allied_ids | relationship_allies | protected_ids
