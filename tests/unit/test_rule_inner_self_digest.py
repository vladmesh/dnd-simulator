"""Rules-only coverage for deterministic inner-self digestion."""

from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from dnd_simulator.core.character import Alignment
from dnd_simulator.core.inner_self import (
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
from dnd_simulator.rules.inner_self_digest import (
    ALIGNMENT_SHIFT_THRESHOLD,
    DigestContext,
    apply_delta,
    derive_delta,
    shift_alignment,
)


def _event(event_type: EventType, actor_id: str | None, target_id: str | None) -> BufferedPerceivedEvent:
    return BufferedPerceivedEvent(event_type, actor_id, target_id, "event", 1)


def _digest(core: InnerSelf, *events: BufferedPerceivedEvent, allies: frozenset[str] = frozenset()) -> InnerSelf:
    return apply_delta(core, derive_delta(core, list(events), DigestContext("self", allies)))


def test_attacked_creates_hate_and_angry_mood() -> None:
    result = _digest(InnerSelf(), _event(EventType.ENTITY_ATTACK, "attacker", "self"))

    assert result.relations == [Relationship("attacker", RelationshipType.HATES)]
    assert result.mood is Mood.ANGRY


def test_repeated_attacks_strengthen_hate_without_exceeding_maximum() -> None:
    core = InnerSelf(relations=[Relationship("attacker", RelationshipType.HATES, 95)])
    result = _digest(
        core,
        _event(EventType.ENTITY_ATTACK, "attacker", "self"),
        _event(EventType.OPPORTUNITY_ATTACK, "attacker", "self"),
    )

    assert result.relations == [Relationship("attacker", RelationshipType.HATES, 100)]


def test_opportunity_attack_log_does_not_double_count_resolved_attack_evidence() -> None:
    victim = InnerSelf(relations=[Relationship("attacker", RelationshipType.HATES, 20)])
    victim_result = _digest(
        victim,
        _event(EventType.ENTITY_ATTACK, "attacker", "self"),
        _event(EventType.OPPORTUNITY_ATTACK, "attacker", "self"),
    )
    attacker = InnerSelf(relations=[Relationship("ally", RelationshipType.TRUSTS)])
    attacker_delta = derive_delta(
        attacker,
        [
            _event(EventType.ENTITY_ATTACK, "self", "ally"),
            _event(EventType.OPPORTUNITY_ATTACK, "self", "ally"),
        ],
        DigestContext("self"),
    )

    assert victim_result.relations == [Relationship("attacker", RelationshipType.HATES, 30)]
    assert attacker_delta.law_chaos_delta == 1
    assert attacker_delta.good_evil_delta == 1


@pytest.mark.parametrize(
    ("alignment", "accumulation", "expected"),
    [
        (Alignment.LAWFUL_NEUTRAL, AlignmentAccumulation(ALIGNMENT_SHIFT_THRESHOLD, 0), Alignment.TRUE_NEUTRAL),
        (Alignment.CHAOTIC_NEUTRAL, AlignmentAccumulation(-ALIGNMENT_SHIFT_THRESHOLD, 0), Alignment.TRUE_NEUTRAL),
        (Alignment.NEUTRAL_GOOD, AlignmentAccumulation(0, ALIGNMENT_SHIFT_THRESHOLD), Alignment.TRUE_NEUTRAL),
        (Alignment.NEUTRAL_EVIL, AlignmentAccumulation(0, -ALIGNMENT_SHIFT_THRESHOLD), Alignment.TRUE_NEUTRAL),
    ],
    ids=["toward_chaos", "toward_law", "toward_evil", "toward_good"],
)
def test_shift_alignment_moves_one_axis_one_step(
    alignment: Alignment, accumulation: AlignmentAccumulation, expected: Alignment
) -> None:
    shifted, remaining = shift_alignment(alignment, accumulation)

    assert shifted is expected
    assert remaining == AlignmentAccumulation(
        law_chaos=int(accumulation.law_chaos * 0.5),
        good_evil=int(accumulation.good_evil * 0.5),
    )


def test_shift_alignment_ignores_pressure_below_threshold_without_mutating_input() -> None:
    accumulation = AlignmentAccumulation(ALIGNMENT_SHIFT_THRESHOLD - 1, -(ALIGNMENT_SHIFT_THRESHOLD - 1))

    shifted, remaining = shift_alignment(Alignment.TRUE_NEUTRAL, accumulation)

    assert shifted is Alignment.TRUE_NEUTRAL
    assert remaining == accumulation
    assert remaining is not accumulation


def test_shift_alignment_hysteresis_requires_more_than_one_opposite_evidence_step() -> None:
    shifted, remaining = shift_alignment(Alignment.LAWFUL_NEUTRAL, AlignmentAccumulation(ALIGNMENT_SHIFT_THRESHOLD, 0))
    after_one_opposite, opposite_remaining = shift_alignment(
        shifted, AlignmentAccumulation(remaining.law_chaos - 1, remaining.good_evil)
    )
    shifted_again, _ = shift_alignment(shifted, AlignmentAccumulation(ALIGNMENT_SHIFT_THRESHOLD, 0))

    assert after_one_opposite is Alignment.TRUE_NEUTRAL
    assert opposite_remaining.law_chaos == 0
    assert shifted_again is Alignment.CHAOTIC_NEUTRAL


@pytest.mark.parametrize(
    ("alignment", "pressure", "expected"),
    [
        (Alignment.LAWFUL_NEUTRAL, 6, Alignment.TRUE_NEUTRAL),
        (Alignment.LAWFUL_NEUTRAL, 10, Alignment.TRUE_NEUTRAL),
        (Alignment.CHAOTIC_NEUTRAL, -6, Alignment.TRUE_NEUTRAL),
        (Alignment.CHAOTIC_NEUTRAL, -10, Alignment.TRUE_NEUTRAL),
    ],
    ids=["positive_double_threshold", "positive_large", "negative_double_threshold", "negative_large"],
)
def test_shift_alignment_caps_overshoot_before_next_digest(
    alignment: Alignment, pressure: int, expected: Alignment
) -> None:
    shifted, remaining = shift_alignment(alignment, AlignmentAccumulation(law_chaos=pressure))
    shifted_again, remaining_again = shift_alignment(shifted, remaining)

    assert shifted is expected
    assert abs(remaining.law_chaos) == ALIGNMENT_SHIFT_THRESHOLD - 1
    assert shifted_again is expected
    assert remaining_again == remaining


@pytest.mark.parametrize(
    ("alignment", "accumulation"),
    [
        (Alignment.CHAOTIC_NEUTRAL, AlignmentAccumulation(99, 0)),
        (Alignment.LAWFUL_NEUTRAL, AlignmentAccumulation(-99, 0)),
        (Alignment.NEUTRAL_EVIL, AlignmentAccumulation(0, 99)),
        (Alignment.NEUTRAL_GOOD, AlignmentAccumulation(0, -99)),
    ],
    ids=["chaotic", "lawful", "evil", "good"],
)
def test_shift_alignment_caps_pressure_at_terminal_axis(
    alignment: Alignment, accumulation: AlignmentAccumulation
) -> None:
    shifted, remaining = shift_alignment(alignment, accumulation)

    assert shifted is alignment
    assert max(abs(remaining.law_chaos), abs(remaining.good_evil)) == ALIGNMENT_SHIFT_THRESHOLD - 1


@pytest.mark.parametrize(
    ("core", "allies"),
    [
        (InnerSelf(relations=[Relationship("ally", RelationshipType.LOVES)]), frozenset()),
        (InnerSelf(goals=[TypedGoal(GoalType.PROTECT, "ally")]), frozenset()),
        (InnerSelf(), frozenset({"ally"})),
    ],
    ids=["relationship", "protect_goal", "caller_context"],
)
def test_ally_death_causes_grief(core: InnerSelf, allies: frozenset[str]) -> None:
    result = _digest(core, _event(EventType.ENTITY_DIED, None, "ally"), allies=allies)

    assert result.mood is Mood.GRIEVING


def test_goal_deaths_update_only_matching_active_typed_goals() -> None:
    core = InnerSelf(
        goals=[
            TypedGoal(GoalType.KILL, "enemy"),
            TypedGoal(GoalType.PROTECT, "ward"),
            TypedGoal(GoalType.KILL, "finished", GoalStatus.ACHIEVED),
            TypedGoal(GoalType.PROTECT, "lost", GoalStatus.FAILED),
        ]
    )
    result = _digest(
        core,
        _event(EventType.ENTITY_DIED, None, "enemy"),
        _event(EventType.ENTITY_DIED, None, "ward"),
        _event(EventType.ENTITY_DIED, None, "finished"),
        _event(EventType.ENTITY_DIED, None, "lost"),
    )

    assert [goal.status for goal in result.goals if isinstance(goal, TypedGoal)] == [
        GoalStatus.ACHIEVED,
        GoalStatus.FAILED,
        GoalStatus.ACHIEVED,
        GoalStatus.FAILED,
    ]


def test_own_attack_on_ally_accumulates_chaos_and_evil_evidence() -> None:
    core = InnerSelf(relations=[Relationship("ally", RelationshipType.TRUSTS)], alignment=AlignmentAccumulation(3, -2))
    result = _digest(core, _event(EventType.ENTITY_ATTACK, "self", "ally"))

    assert result.alignment == AlignmentAccumulation(law_chaos=4, good_evil=-1)


def test_other_creatures_actions_do_not_accumulate_alignment_evidence() -> None:
    result = _digest(
        InnerSelf(),
        _event(EventType.ENTITY_ATTACK, "stranger", "ally"),
        allies=frozenset({"ally"}),
    )

    assert result.alignment == AlignmentAccumulation()


def test_self_attack_does_not_create_hate_relation_to_self() -> None:
    result = _digest(InnerSelf(), _event(EventType.ENTITY_ATTACK, "self", "self"))

    assert result.relations == []
    assert result.mood is Mood.NEUTRAL


def test_grief_has_priority_over_anger() -> None:
    core = InnerSelf(relations=[Relationship("ally", RelationshipType.LOYAL_TO)])
    result = _digest(
        core,
        _event(EventType.ENTITY_ATTACK, "attacker", "self"),
        _event(EventType.ENTITY_DIED, None, "ally"),
    )

    assert result.mood is Mood.GRIEVING


def test_derivation_is_deterministic_and_does_not_mutate_input() -> None:
    core = InnerSelf(
        relations=[Relationship("ally", RelationshipType.TRUSTS)],
        perceived_event_buffer=[_event(EventType.ENTITY_ATTACK, "attacker", "self")],
    )
    before = deepcopy(core)
    events = list(core.perceived_event_buffer)
    context = DigestContext("self")

    first = derive_delta(core, events, context)
    second = derive_delta(core, events, context)
    applied = apply_delta(core, first)

    assert first == second
    assert core == before
    assert applied is not core
    assert applied.perceived_event_buffer == []


def test_rules_module_only_depends_on_core_domain() -> None:
    source = Path("src/dnd_simulator/rules/inner_self_digest.py").read_text()
    imported_modules = [
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    ]

    prohibited_prefixes = (
        "dnd_simulator.layers",
        "dnd_simulator.service",
        "dnd_simulator.llm",
        "dnd_simulator.adapters",
    )
    assert not any(module.startswith(prohibited_prefixes) for module in imported_modules)
