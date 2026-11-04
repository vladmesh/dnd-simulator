"""Tests for FileDispatchProcessor routing of structured log entries to JSONL files."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from dnd_simulator.logging_file_dispatch import FileDispatchProcessor


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _files(base: Path) -> set[str]:
    return {str(p.relative_to(base)) for p in base.rglob("*") if p.is_file()}


class TestRouting:
    def test_plain_event_goes_only_to_full_log_and_passes_through(self, tmp_path: Path) -> None:
        proc = FileDispatchProcessor(tmp_path)
        event = {"event": "hello", "session_id": "s1"}

        result = proc(None, "info", event)

        assert result is event
        assert _files(tmp_path) == {"session_s1/full.jsonl"}
        assert _lines(tmp_path / "session_s1" / "full.jsonl") == [{"event": "hello", "session_id": "s1"}]

    def test_missing_session_id_uses_unknown_session(self, tmp_path: Path) -> None:
        FileDispatchProcessor(tmp_path)(None, "info", {"event": "orphan"})

        assert _files(tmp_path) == {"session_unknown/full.jsonl"}

    def test_llm_domain_with_entity_fans_out(self, tmp_path: Path) -> None:
        FileDispatchProcessor(tmp_path)(
            None, "info", {"event": "llm_call", "session_id": "s", "domain": "llm", "entity_id": "goblin"}
        )

        assert _files(tmp_path) == {
            "session_s/full.jsonl",
            "session_s/llm/all.jsonl",
            "session_s/llm/goblin.jsonl",
            "session_s/entities/goblin.jsonl",
        }

    def test_llm_domain_without_entity(self, tmp_path: Path) -> None:
        FileDispatchProcessor(tmp_path)(None, "info", {"event": "llm_call", "session_id": "s", "domain": "llm.client"})

        assert _files(tmp_path) == {"session_s/full.jsonl", "session_s/llm/all.jsonl"}

    def test_combat_summary_only_for_start_and_end(self, tmp_path: Path) -> None:
        proc = FileDispatchProcessor(tmp_path)
        proc(None, "info", {"event": "combat_start", "session_id": "s", "domain": "combat"})
        proc(None, "info", {"event": "attack", "session_id": "s", "domain": "combat"})
        proc(None, "info", {"event": "combat_end", "session_id": "s", "domain": "combat"})

        summary = _lines(tmp_path / "session_s" / "combat" / "summary.jsonl")
        assert [e["event"] for e in summary] == ["combat_start", "combat_end"]
        assert len(_lines(tmp_path / "session_s" / "full.jsonl")) == 3

    def test_action_domain_splits_failed(self, tmp_path: Path) -> None:
        proc = FileDispatchProcessor(tmp_path)
        proc(None, "info", {"event": "a1", "session_id": "s", "domain": "action", "success": True})
        proc(None, "info", {"event": "a2", "session_id": "s", "domain": "action", "success": False})
        proc(None, "info", {"event": "a3", "session_id": "s", "domain": "action"})

        assert [e["event"] for e in _lines(tmp_path / "session_s" / "actions" / "all.jsonl")] == ["a1", "a2", "a3"]
        assert [e["event"] for e in _lines(tmp_path / "session_s" / "actions" / "failed.jsonl")] == ["a2"]

    def test_round_domain(self, tmp_path: Path) -> None:
        FileDispatchProcessor(tmp_path)(None, "info", {"event": "round_start", "session_id": "s", "domain": "round"})

        assert _files(tmp_path) == {"session_s/full.jsonl", "session_s/round/all.jsonl"}

    def test_non_json_values_and_unicode_are_written(self, tmp_path: Path) -> None:
        FileDispatchProcessor(tmp_path)(None, "info", {"event": "привет", "session_id": "s", "path": Path("x/y")})

        raw = (tmp_path / "session_s" / "full.jsonl").read_text(encoding="utf-8")
        assert "привет" in raw
        assert _lines(tmp_path / "session_s" / "full.jsonl")[0]["path"] == str(Path("x/y"))


class TestExcInfo:
    def test_exc_info_is_formatted_in_file_but_event_dict_untouched(self, tmp_path: Path) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            exc = sys.exc_info()
        event: dict[str, Any] = {"event": "failed", "session_id": "s", "exc_info": exc}

        result = FileDispatchProcessor(tmp_path)(None, "error", event)

        assert result is event
        assert result["exc_info"] is exc
        assert "exception" not in result
        (record,) = _lines(tmp_path / "session_s" / "full.jsonl")
        assert "exc_info" not in record
        assert "ValueError: boom" in record["exception"]


class TestLlmContext:
    def test_context_written_as_separate_json_file(self, tmp_path: Path) -> None:
        event = {
            "event": "llm_context",
            "session_id": "s",
            "domain": "llm.context",
            "entity_id": "orc",
            "timestamp": "2026-03-24T10:43:08.154Z",
            "prompt": "Привет",
        }

        result = FileDispatchProcessor(tmp_path)(None, "debug", event)

        assert result is event
        assert _files(tmp_path) == {"session_s/llm/contexts/orc_10-43-08.json"}
        path = tmp_path / "session_s" / "llm" / "contexts" / "orc_10-43-08.json"
        assert json.loads(path.read_text(encoding="utf-8")) == event

    def test_context_without_entity_or_timestamp_uses_unknown(self, tmp_path: Path) -> None:
        FileDispatchProcessor(tmp_path)(None, "debug", {"event": "ctx", "session_id": "s", "domain": "llm.context"})

        assert _files(tmp_path) == {"session_s/llm/contexts/unknown_unknown.json"}

    def test_context_with_short_timestamp_uses_unknown_time(self, tmp_path: Path) -> None:
        FileDispatchProcessor(tmp_path)(
            None,
            "debug",
            {"event": "ctx", "session_id": "s", "domain": "llm.context", "entity_id": "e", "timestamp": "2026-03-24"},
        )

        assert _files(tmp_path) == {"session_s/llm/contexts/e_unknown.json"}
