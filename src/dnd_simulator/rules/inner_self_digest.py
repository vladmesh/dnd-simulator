"""Deterministic inner-self digestion rules.

The rules consume perceived events in their buffered order.  An attack against
the core bearer creates or strengthens ``hates`` and proposes ``angry``; the
death of an ally proposes ``grieving``.  Death completes active ``kill`` goals
and fails active ``protect`` goals. A core bearer's own attack on an ally adds
one step each toward chaos and evil. ``ENTITY_ATTACK`` is the canonical evidence
for a resolved attack; ``OPPORTUNITY_ATTACK`` is a separate combat-log event and
is deliberately not counted again. Positive ``law_chaos`` pressure points toward
chaos and negative pressure toward law; positive ``good_evil`` pressure points
toward evil and negative pressure toward good.

When several moods are evidenced, ``MOOD_PRIORITY`` chooses the highest one,
so grieving wins over angry regardless of event order.
"""

from __future__ import annotations

from dataclasses import dataclass

from dnd_simulator.core.character import Alignment
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
ALIGNMENT_SHIFT_THRESHOLD = 3
ALIGNMENT_HYSTERESIS_RETENTION = 0.5
MOOD_PRIORITY: dict[Mood, int] = {Mood.ANGRY: 1, Mood.GRIEVING: 2}

_ALIGNMENT_FROM_AXES: dict[tuple[int, int], Alignment] = {
    (0, 0): Alignment.LAWFUL_GOOD,
    (1, 0): Alignment.NEUTRAL_GOOD,
    (2, 0): Alignment.CHAOTIC_GOOD,
    (0, 1): Alignment.LAWFUL_NEUTRAL,
    (1, 1): Alignment.TRUE_NEUTRAL,
    (2, 1): Alignment.CHAOTIC_NEUTRAL,
    (0, 2): Alignment.LAWFUL_EVIL,
    (1, 2): Alignment.NEUTRAL_EVIL,
    (2, 2): Alignment.CHAOTIC_EVIL,
}
_AXES_FROM_ALIGNMENT = {alignment: axes for axes, alignment in _ALIGNMENT_FROM_AXES.items()}


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
        # An opportunity attack emits its resolved ENTITY_ATTACK before its
        # OPPORTUNITY_ATTACK log event. Only the resolved attack is evidence.
        if event.event_type is EventType.ENTITY_ATTACK:
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
    """Return a rules-only core with *delta* applied, without mutating *core*.

    The returned free layer is intentionally empty; the entities digest entry
    point restores journal, thoughts, and current conversation from *core*.
    """
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
        # The free layer is retained by the entities digest entry point. Rules
        # deliberately never read journal or thoughts, which only LLM code owns.
        journal="",
        thoughts=[],
        current_conversation="",
        perceived_event_buffer=[],
    )


def shift_alignment(
    alignment: Alignment, accumulation: AlignmentAccumulation
) -> tuple[Alignment, AlignmentAccumulation]:
    """Move at most one alignment step per axis and return fresh values.

    Three evidence steps form a threshold. Positive ``law_chaos`` moves
    lawful → neutral → chaotic, while negative pressure moves the other way;
    positive ``good_evil`` moves good → neutral → evil, while negative pressure
    moves the other way. The axes are independent.

    After a move, signed pressure is halved toward zero and then capped to
    ``±(threshold - 1)``. Thus retained pressure is always strictly below the
    threshold, including an overshooting batch, and a later shift needs new
    evidence. One opposite evidence step cannot reverse a threshold crossing.
    At a terminal axis value, pressure pushing beyond that edge is clamped to
    ``±(threshold - 1)``: it cannot grow unbounded, and opposite evidence must
    first work through the retained pressure. Inputs are never mutated.
    """
    law_chaos, good_evil = _AXES_FROM_ALIGNMENT[alignment]
    law_chaos, law_evidence = _shift_axis(law_chaos, accumulation.law_chaos)
    good_evil, good_evidence = _shift_axis(good_evil, accumulation.good_evil)
    return _ALIGNMENT_FROM_AXES[(law_chaos, good_evil)], AlignmentAccumulation(law_evidence, good_evidence)


def _shift_axis(position: int, pressure: int) -> tuple[int, int]:
    """Apply one threshold crossing to one ordered three-value alignment axis."""
    if pressure >= ALIGNMENT_SHIFT_THRESHOLD:
        if position < 2:
            return position + 1, min(int(pressure * ALIGNMENT_HYSTERESIS_RETENTION), ALIGNMENT_SHIFT_THRESHOLD - 1)
        return position, ALIGNMENT_SHIFT_THRESHOLD - 1
    if pressure <= -ALIGNMENT_SHIFT_THRESHOLD:
        if position > 0:
            return position - 1, max(int(pressure * ALIGNMENT_HYSTERESIS_RETENTION), -(ALIGNMENT_SHIFT_THRESHOLD - 1))
        return position, -(ALIGNMENT_SHIFT_THRESHOLD - 1)
    return position, pressure


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
