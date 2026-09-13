"""Pure PASS/WARN classification for the manual live inner-self scenario."""

from __future__ import annotations

from typing import TypedDict


class Check(TypedDict):
    name: str
    passed: bool


def _core(snapshot: dict[str, object]) -> dict[str, object]:
    """Return the writable core and rules-derived alignment from an API snapshot."""
    keys = ("relations", "mood", "goals", "character_alignment", "alignment_accumulation")
    return {key: snapshot.get(key) for key in keys}


def _count(metrics: dict[str, object], name: str) -> int:
    value = metrics.get(name, 0)
    return value if isinstance(value, int) else 0


def classify_report(
    before: dict[str, object],
    after_combat: dict[str, object],
    after_anchor: dict[str, object],
    metrics: dict[str, object],
) -> list[Check]:
    """Classify supplied snapshots and telemetry without making network calls."""
    accepted = _count(metrics, "accepted_digests")
    fallback = _count(metrics, "fallback_digests")
    core_changed = _core(before) != _core(after_combat) or _core(after_combat) != _core(after_anchor)
    journal_changed = before.get("journal") != after_combat.get("journal") or after_combat.get(
        "journal"
    ) != after_anchor.get("journal")
    return [
        {"name": "digest accepted", "passed": bool(accepted)},
        {"name": "rules fallback observed", "passed": bool(fallback)},
        {"name": "thought recorded", "passed": bool(after_combat.get("thoughts") or after_anchor.get("thoughts"))},
        {"name": "core changed after observed events", "passed": core_changed},
        {"name": "journal changed after observed events", "passed": journal_changed},
        {"name": "digest response shape available", "passed": bool(metrics.get("digest_response_formats"))},
        {"name": "tool-call retries observed", "passed": bool(metrics.get("accepted_tool_calls", 0))},
    ]
