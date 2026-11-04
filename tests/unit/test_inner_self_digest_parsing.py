from __future__ import annotations

import json

import pytest

from dnd_simulator.llm.inner_self_digest import (
    LlmDigestRejectedError,
    _evidence,
    _parse_goal,
    _parse_relation,
    _parse_response,
    _remove_single_code_fence,
    _require_keys,
    _require_str,
)


def _response_payload(**changes: object) -> str:
    payload: dict[str, object] = {
        "relations": [{"target_id": "rival", "type": "hates", "intensity": 70}],
        "mood": "angry",
        "goals": [{"type": "kill", "target_id": "rival", "status": "active"}],
        "journal": "Rival attacked at the square.",
        "alignment_evidence": {"law_chaos": 0, "good_evil": 0},
    }
    payload.update(changes)
    return json.dumps(payload)


def test_remove_single_code_fence_leaves_non_matching_input_untouched() -> None:
    response = object()

    assert _remove_single_code_fence(response) is response


@pytest.mark.parametrize(
    "response",
    [
        "```json",
        "```yaml\n{}\n```",
        "```json\n{}\n``` trailing",
        "not fenced",
    ],
)
def test_remove_single_code_fence_leaves_non_fences_untouched(response: str) -> None:
    assert _remove_single_code_fence(response) == response


def test_remove_single_code_fence_accepts_one_complete_json_fence() -> None:
    assert _remove_single_code_fence("```json\n{}\n```") == "{}"


def test_parse_response_rejects_non_object_payload() -> None:
    with pytest.raises(LlmDigestRejectedError, match="response is not an object"):
        _parse_response(json.dumps([]), {"rival"}, "self")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"relations": "oops"}, "relations must be a list"),
        ({"goals": "oops"}, "goals must be a list"),
        ({"journal": 1}, "journal must be a string"),
        ({"mood": "vengeful"}, "invalid mood"),
    ],
)
def test_parse_response_rejects_invalid_core_fields(changes: dict[str, object], message: str) -> None:
    with pytest.raises(LlmDigestRejectedError, match=message):
        _parse_response(_response_payload(**changes), {"rival"}, "self")


def test_parse_response_rejects_alignment_evidence_that_is_not_an_object() -> None:
    with pytest.raises(LlmDigestRejectedError, match="alignment_evidence must be an object"):
        _parse_response(_response_payload(alignment_evidence=[]), {"rival"}, "self")


@pytest.mark.parametrize(
    ("item", "message"),
    [
        ([], "relationship must be an object"),
        ({"target_id": "self", "type": "hates", "intensity": 50}, "unknown relationship target"),
        ({"target_id": "rival", "type": "enemy", "intensity": 50}, "invalid relationship type"),
        ({"target_id": "rival", "type": "hates", "intensity": 0}, "invalid relationship intensity"),
        ({"target_id": "rival", "type": "hates", "intensity": "high"}, "invalid relationship intensity"),
    ],
)
def test_parse_relation_rejects_invalid_items(item: object, message: str) -> None:
    with pytest.raises(LlmDigestRejectedError, match=message):
        _parse_relation(item, {"rival"}, "self")


@pytest.mark.parametrize(
    ("item", "message"),
    [
        ([], "goal must be an object"),
        ({"type": "kill", "target_id": "stranger", "status": "active"}, "unknown goal target"),
        ({"type": "dance", "target_id": "ally", "status": "active"}, "invalid typed goal"),
        ({"type": "kill", "target_id": "ally", "status": "paused"}, "invalid typed goal"),
        ({"text": "   ", "status": "active"}, "freeform goal text is empty"),
        ({"text": "Escape", "status": "paused"}, "invalid freeform goal"),
        ({"type": "kill", "target_id": "ally"}, "invalid goal fields"),
        ({"text": "Escape", "status": "active", "extra": True}, "invalid goal fields"),
    ],
)
def test_parse_goal_rejects_invalid_items(item: object, message: str) -> None:
    with pytest.raises(LlmDigestRejectedError, match=message):
        _parse_goal(item, {"ally"})


@pytest.mark.parametrize(
    ("value", "field", "message"),
    [
        (2, "law_chaos", "invalid law_chaos evidence"),
        (1.0, "good_evil", "invalid good_evil evidence"),
        ("1", "law_chaos", "invalid law_chaos evidence"),
    ],
)
def test_evidence_rejects_invalid_values(value: object, field: str, message: str) -> None:
    with pytest.raises(LlmDigestRejectedError, match=message):
        _evidence(value, field)


def test_require_keys_rejects_unexpected_fields() -> None:
    with pytest.raises(LlmDigestRejectedError, match="unexpected response fields"):
        _require_keys({"relations": [], "extra": 1}, {"relations"}, "response")


@pytest.mark.parametrize(
    ("value", "field", "message"),
    [
        (None, "mood", "mood must be a string"),
        (0, "goal type", "goal type must be a string"),
    ],
)
def test_require_str_rejects_non_strings(value: object, field: str, message: str) -> None:
    with pytest.raises(LlmDigestRejectedError, match=message):
        _require_str(value, field)
