"""Pure checks for the manual live inner-self acceptance scenario."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_simulator.live_inner_self_report import classify_report, parse_session_jsonl


def _snapshot(*, mood: str = "alerted", journal: str = "", thoughts: list[str] | None = None) -> dict[str, object]:
    return {
        "relations": [{"target_id": "player", "type": "loyal_to", "intensity": 80}],
        "mood": mood,
        "goals": [{"kind": "typed", "type": "protect", "target_id": "player", "status": "active"}],
        "character_alignment": "true_neutral",
        "alignment_accumulation": {"law_chaos": 0, "good_evil": 0},
        "journal": journal,
        "thoughts": thoughts or [],
    }


def test_classify_report_accepts_fenced_digest_with_thought_and_core_change() -> None:
    checks = classify_report(
        _snapshot(),
        _snapshot(mood="angry", journal="The attack was unprovoked.", thoughts=["Protect the anchor."]),
        _snapshot(mood="angry", journal="The attack was unprovoked.", thoughts=["Protect the anchor."]),
        {
            "accepted_digests": 1,
            "fallback_digests": 0,
            "retries_before_valid": [1],
            "digest_response_formats": ["fenced_json"],
        },
        completed=True,
    )

    assert {check["name"] for check in checks if check["status"] == "PASS"} >= {
        "LLM digest accepted",
        "Thought recorded",
        "Core changed after observed events",
        "Journal changed after observed events",
        "Digest response shape available",
        "Tool-call retries observed",
    }


def test_classify_report_marks_fallback_and_missing_evidence_as_warnings() -> None:
    checks = classify_report(
        _snapshot(),
        _snapshot(),
        _snapshot(),
        {"accepted_digests": 0, "fallback_digests": 1, "digest_response_formats": ["bare_json"]},
        completed=True,
    )
    outcome = {check["name"]: check["status"] for check in checks}

    assert outcome["LLM digest accepted"] == "WARN"
    assert outcome["Rules fallback used"] == "INFO"
    assert outcome["Thought recorded"] == "INFO"
    assert outcome["Core changed after observed events"] == "INFO"
    assert outcome["Journal changed after observed events"] == "INFO"
    assert outcome["Digest response shape available"] == "PASS"
    assert outcome["Tool-call retries observed"] == "INFO"


def test_log_parser_uses_one_session_and_keeps_retry_counts() -> None:
    lines = [
        json.dumps({"session_id": "other", "event": "inner_self_llm_digest_accepted", "response_format": "bare_json"}),
        json.dumps({"session_id": "live", "event": "inner_self_llm_digest_rejected", "entity_id": "live_npc"}),
        json.dumps({"session_id": "live", "event": "llm_tool_call_accepted", "retries": 2}),
    ]

    metrics = parse_session_jsonl(lines, "live")

    assert metrics["accepted_digests"] == 0
    assert metrics["fallback_digests"] == 1
    assert metrics["retries_before_valid"] == [2]


def test_log_reader_uses_only_the_current_session_full_stream(tmp_path: Path) -> None:
    from scripts import live_inner_self

    session_dir = tmp_path / "session_live"
    session_dir.mkdir()
    current_record = {"session_id": "live", "event": "llm_tool_call_accepted", "retries": 1}
    (session_dir / "full.jsonl").write_text(json.dumps(current_record))
    duplicate = session_dir / "llm"
    duplicate.mkdir()
    (duplicate / "all.jsonl").write_text(
        json.dumps({"session_id": "live", "event": "llm_tool_call_accepted", "retries": 9})
    )

    metrics = live_inner_self._read_metrics(tmp_path, "live")

    assert metrics["retries_before_valid"] == [1]


def test_missing_model_configuration_skips_without_network(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(SystemExit) as error:
        from scripts import live_inner_self

        live_inner_self.main()

    assert error.value.code == 2
    assert "SKIPPED / NOT RUNNABLE" in capsys.readouterr().out
