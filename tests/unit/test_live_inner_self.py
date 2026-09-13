"""Pure checks for the manual live inner-self acceptance scenario."""

from __future__ import annotations

import pytest

from dnd_simulator.live_inner_self_report import classify_report


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
            "accepted_tool_calls": 2,
            "digest_response_formats": ["fenced_json"],
        },
    )

    assert {check["name"] for check in checks if check["passed"]} >= {
        "digest accepted",
        "thought recorded",
        "core changed after observed events",
        "journal changed after observed events",
        "digest response shape available",
        "tool-call retries observed",
    }


def test_classify_report_marks_fallback_and_missing_evidence_as_warnings() -> None:
    checks = classify_report(
        _snapshot(),
        _snapshot(),
        _snapshot(),
        {"accepted_digests": 0, "fallback_digests": 1, "digest_response_formats": ["bare_json"]},
    )
    outcome = {check["name"]: check["passed"] for check in checks}

    assert outcome["digest accepted"] is False
    assert outcome["rules fallback observed"] is True
    assert outcome["thought recorded"] is False
    assert outcome["core changed after observed events"] is False
    assert outcome["journal changed after observed events"] is False
    assert outcome["digest response shape available"] is True
    assert outcome["tool-call retries observed"] is False


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
