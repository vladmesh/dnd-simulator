"""LLM inner-self digestion is strict, bounded, and optional by brain type."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from dnd_simulator.core.character import Alignment, NpcRole
from dnd_simulator.core.inner_self import (
    AlignmentAccumulation,
    BufferedPerceivedEvent,
    DigestBoundary,
    GoalStatus,
    GoalType,
    InnerSelf,
    Mood,
    Relationship,
    RelationshipType,
    TypedGoal,
)
from dnd_simulator.core.models import EventType
from dnd_simulator.layers.entities.inner_self_digest import digest, dormify
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.llm.brain import LlmBrain
from dnd_simulator.llm.inner_self_digest import JOURNAL_LIMIT, build_messages
from dnd_simulator.rules.rule_brain import RuleBrain


class FakeClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[list[dict[str, object]]] = []
        self.options: list[dict[str, object]] = []

    def generate(self, messages: list[dict[str, object]], **kwargs: object) -> str:
        self.calls.append(messages)
        self.options.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        assert isinstance(self.response, str)
        return self.response


def _npc(brain: object, core: InnerSelf) -> Npc:
    return Npc(
        id="npc",
        name="Witness",
        location_id="square",
        role=NpcRole.GUARD,
        personality="Alert.",
        settlement_id="town",
        alignment=Alignment.TRUE_NEUTRAL,
        brain=brain,  # type: ignore[arg-type]
        inner_self=core,
    )


def _event(event_type: EventType = EventType.ENTITY_ATTACK) -> BufferedPerceivedEvent:
    return BufferedPerceivedEvent(event_type, "rival", "npc", "Rival attacks Witness.", 123)


def _response(**changes: object) -> str:
    payload: dict[str, object] = {
        "relations": [{"target_id": "rival", "type": "hates", "intensity": 70}],
        "mood": "angry",
        "goals": [{"type": "kill", "target_id": "rival", "status": "active"}],
        "journal": "Rival attacked at the square.",
        "alignment_evidence": {"law_chaos": 0, "good_evil": 0},
    }
    payload.update(changes)
    return json.dumps(payload)


def _digest_with_response(response: object) -> tuple[Npc, FakeClient]:
    client = FakeClient(response)
    npc = _npc(
        LlmBrain(client),  # type: ignore[arg-type]
        InnerSelf(journal="Before.", perceived_event_buffer=[_event()]),
    )
    digest(npc, DigestBoundary.COMBAT_ENDED)
    return npc, client


def test_valid_llm_digest_replaces_core_preserves_llm_only_buffers_and_shifts_after_evidence() -> None:
    client = FakeClient(
        _response(
            mood="suspicious",
            journal="x" * (JOURNAL_LIMIT + 10),
            alignment_evidence={"law_chaos": 1, "good_evil": -1},
        )
    )
    core = InnerSelf(
        alignment=AlignmentAccumulation(law_chaos=2, good_evil=2),
        journal="Before.",
        thoughts=["Stay alert."],
        current_conversation="Talking with the mayor.",
        perceived_event_buffer=[_event(EventType.ENTITY_SAY)],
    )
    npc = _npc(LlmBrain(client), core)  # type: ignore[arg-type]

    digest(npc, DigestBoundary.COMBAT_ENDED)

    assert len(client.calls) == 1
    assert npc.inner_self is not None
    assert npc.inner_self.mood is Mood.SUSPICIOUS
    assert npc.inner_self.relations == [Relationship("rival", RelationshipType.HATES, 70)]
    assert npc.inner_self.goals == [TypedGoal(GoalType.KILL, "rival", GoalStatus.ACTIVE)]
    assert npc.inner_self.journal == "x" * JOURNAL_LIMIT
    assert npc.inner_self.thoughts == ["Stay alert."]
    assert npc.inner_self.current_conversation == "Talking with the mayor."
    # Rule proposal starts at 2; evidence is added before shift_alignment sees 3.
    assert npc.alignment is Alignment.CHAOTIC_NEUTRAL
    assert npc.inner_self.alignment == AlignmentAccumulation(law_chaos=1, good_evil=1)
    assert npc.inner_self.perceived_event_buffer == []


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        "[]",
        RuntimeError("network timeout"),
        _response(mood="vengeful"),
        _response(relations=[{"target_id": "rival", "type": "enemy", "intensity": 50}]),
        _response(relations=[{"target_id": "rival", "type": "hates", "intensity": 101}]),
        _response(
            relations=[
                {"target_id": "rival", "type": "hates", "intensity": 50},
                {"target_id": "rival", "type": "hates", "intensity": 60},
            ]
        ),
        _response(relations=[{"target_id": "stranger", "type": "hates", "intensity": 50}]),
        _response(goals=[{"text": "   ", "status": "active"}]),
        _response(journal=None),
        _response(alignment_evidence={"law_chaos": 2, "good_evil": 0}),
        _response(extra="forbidden"),
    ],
)
def test_rejected_llm_response_applies_complete_rule_proposal_and_discards_buffer(response: object) -> None:
    npc, client = _digest_with_response(response)

    assert len(client.calls) == 1
    assert npc.inner_self is not None
    assert npc.inner_self.relations == [Relationship("rival", RelationshipType.HATES, 50)]
    assert npc.inner_self.mood is Mood.ANGRY
    assert npc.inner_self.goals == []
    assert npc.inner_self.journal == "Before."
    assert npc.inner_self.perceived_event_buffer == []


def test_rule_brain_never_calls_configured_llm_client() -> None:
    client = FakeClient(_response())
    npc = _npc(RuleBrain(), InnerSelf(journal="Before.", perceived_event_buffer=[_event()]))

    digest(npc, DigestBoundary.COMBAT_ENDED)

    assert client.calls == []
    assert npc.inner_self is not None
    assert npc.inner_self.journal == "Before."
    assert npc.inner_self.mood is Mood.ANGRY


def test_dormify_absorbs_llm_client_failure_after_clearing_buffer() -> None:
    client = FakeClient(RuntimeError("offline"))
    npc = _npc(LlmBrain(client), InnerSelf(journal="Before.", perceived_event_buffer=[_event()]))  # type: ignore[arg-type]

    dormify(npc, digest)

    assert npc.active is False
    assert len(client.calls) == 1
    assert npc.inner_self is not None
    assert npc.inner_self.perceived_event_buffer == []
    assert npc.inner_self.journal == "Before."


def test_prompt_contains_pre_boundary_core_raw_events_thoughts_targets_and_late_proposal() -> None:
    before = InnerSelf(
        relations=[Relationship("old_friend", RelationshipType.TRUSTS)],
        goals=[TypedGoal(GoalType.PROTECT, "ward")],
        thoughts=["Keep the gate closed."],
        journal="Before.",
    )
    proposal = InnerSelf(mood=Mood.ANGRY)
    messages = build_messages(before, [_event()], "combat_ended", proposal, "npc")
    prompt = messages[0]["content"]

    assert isinstance(prompt, str)
    assert "Core before this boundary" in prompt
    assert "Rival attacks Witness." in prompt
    assert "Keep the gate closed." in prompt
    assert '"old_friend"' in prompt and '"ward"' in prompt and '"rival"' in prompt
    assert "RULES PROPOSAL, not an answer" in prompt
    assert prompt.index("Raw perceived events") < prompt.index("RULES PROPOSAL")


@pytest.mark.parametrize("fence", ["```\n{response}\n```", "```json\n{response}\n```"])
def test_digest_accepts_one_json_code_fence(fence: str) -> None:
    npc, _client = _digest_with_response(fence.format(response=_response(mood="suspicious")))

    assert npc.inner_self is not None
    assert npc.inner_self.mood is Mood.SUSPICIOUS


def test_digest_rejects_text_outside_a_code_fence_and_bounds_client_options() -> None:
    npc, client = _digest_with_response("Here is the result:\n```json\n" + _response(mood="suspicious") + "\n```")

    assert npc.inner_self is not None
    assert npc.inner_self.mood is Mood.ANGRY
    assert client.options == [{"max_tokens": 800, "temperature": 0.3, "timeout": 20.0, "max_retries": 0}]


def test_digest_prompt_labels_heard_speech() -> None:
    heard = BufferedPerceivedEvent(EventType.ENTITY_SAY, "rival", "npc", "Rival says: obey me", 123, heard=True)
    prompt = build_messages(InnerSelf(), [heard], "combat_ended", InnerSelf(), "npc")[0]["content"]

    assert isinstance(prompt, str)
    assert "Heard rival say: Rival says: obey me" in prompt


def test_classic_paths_do_not_read_llm_only_journal_or_thoughts() -> None:
    root = Path(__file__).parents[2] / "src" / "dnd_simulator"
    for relative in (
        "rules/rule_brain.py",
        "rules/inner_self_digest.py",
        "layers/entities/models.py",
    ):
        tree = ast.parse((root / relative).read_text())
        reads = [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)]
        assert "journal" not in reads, relative
        assert "thoughts" not in reads, relative
