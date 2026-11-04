"""Coverage for blank and malformed records in live inner-self session logs."""

import json

import pytest

from dnd_simulator.live_inner_self_report import parse_session_jsonl


@pytest.mark.parametrize(
    "ignored_line",
    [
        pytest.param("", id="empty"),
        pytest.param(" \t\n", id="whitespace"),
        pytest.param("not JSON\n", id="malformed-json"),
        pytest.param('{"session_id": "live",', id="truncated-json"),
    ],
)
def test_log_parser_skips_invalid_lines_and_continues_summarizing(ignored_line: str) -> None:
    lines = [
        json.dumps({"session_id": "live", "event": "inner_self_llm_digest_rejected"}),
        ignored_line,
        json.dumps({"session_id": "other", "event": "llm_tool_call_accepted", "retries": 9}),
        json.dumps({"session_id": "live", "event": "inner_self_llm_digest_accepted", "response_format": "bare_json"}),
        json.dumps({"session_id": "live", "event": "llm_tool_call_rejected"}),
        json.dumps({"session_id": "live", "event": "llm_tool_call_accepted", "retries": 2}),
    ]

    metrics = parse_session_jsonl(iter(lines), "live")

    assert metrics == {
        "available": True,
        "accepted_digests": 1,
        "fallback_digests": 1,
        "rejected_tool_calls": 1,
        "accepted_tool_calls": 1,
        "retries_before_valid": [2],
        "digest_response_formats": ["bare_json"],
    }
