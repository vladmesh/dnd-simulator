"""Pure report and log handling for the manual live inner-self scenario."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Literal, TypedDict


class Check(TypedDict):
    name: str
    status: Literal["PASS", "WARN", "INFO"]


def _count(metrics: dict[str, object], name: str) -> int:
    value = metrics.get(name, 0)
    return value if isinstance(value, int) else 0


def parse_session_records(records: Iterable[object], session_id: str) -> dict[str, object]:
    """Summarize records from one log stream, retaining only one session's events."""
    selected = [record for record in records if isinstance(record, dict) and record.get("session_id") == session_id]
    events = [record.get("event") for record in selected]
    accepted = [record for record in selected if record.get("event") == "llm_tool_call_accepted"]
    return {
        "available": True,
        "accepted_digests": events.count("inner_self_llm_digest_accepted"),
        "fallback_digests": events.count("inner_self_llm_digest_rejected"),
        "rejected_tool_calls": events.count("llm_tool_call_rejected"),
        "accepted_tool_calls": len(accepted),
        "retries_before_valid": [
            record.get("retries") for record in accepted if isinstance(record.get("retries"), int)
        ],
        "digest_response_formats": [
            record.get("response_format")
            for record in selected
            if record.get("event") == "inner_self_llm_digest_accepted"
        ],
    }


def parse_session_jsonl(lines: Iterable[str], session_id: str) -> dict[str, object]:
    """Parse one session's ``full.jsonl`` stream without touching the filesystem."""
    records: list[object] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return parse_session_records(records, session_id)


def _core(snapshot: dict[str, object]) -> dict[str, object]:
    keys = ("relations", "mood", "goals", "character_alignment", "alignment_accumulation")
    return {key: snapshot.get(key) for key in keys}


def classify_report(
    before: dict[str, object],
    after_combat: dict[str, object],
    after_anchor: dict[str, object],
    metrics: dict[str, object],
    *,
    completed: bool,
) -> list[Check]:
    """Classify supplied snapshots and telemetry without network or filesystem access."""
    accepted = _count(metrics, "accepted_digests")
    fallback = _count(metrics, "fallback_digests")
    retry_counts = metrics.get("retries_before_valid", [])
    retries = retry_counts if isinstance(retry_counts, list) else []
    core_changed = _core(before) != _core(after_combat) or _core(after_combat) != _core(after_anchor)
    journal_changed = before.get("journal") != after_combat.get("journal") or after_combat.get(
        "journal"
    ) != after_anchor.get("journal")
    return [
        {"name": "Scenario completed", "status": "PASS" if completed else "WARN"},
        {"name": "LLM digest accepted", "status": "PASS" if accepted else "WARN"},
        {"name": "Rules fallback used", "status": "INFO"},
        {"name": "Digest reached an observed boundary", "status": "PASS" if accepted or fallback else "WARN"},
        {
            "name": "Thought recorded",
            "status": "PASS" if after_combat.get("thoughts") or after_anchor.get("thoughts") else "INFO",
        },
        {"name": "Core changed after observed events", "status": "PASS" if core_changed else "INFO"},
        {"name": "Journal changed after observed events", "status": "PASS" if journal_changed else "INFO"},
        {
            "name": "Digest response shape available",
            "status": "PASS" if metrics.get("digest_response_formats") else "INFO",
        },
        {"name": "Tool-call retries observed", "status": "PASS" if any(count > 0 for count in retries) else "INFO"},
    ]
