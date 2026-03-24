"""File dispatch processor — routes structured log entries to denormalized JSONL files.

File structure per session:
    logs/session_{id}/full.jsonl
    logs/session_{id}/llm/all.jsonl
    logs/session_{id}/llm/{entity_id}.jsonl
    logs/session_{id}/llm/contexts/{entity}_{time}.json
    logs/session_{id}/entities/{entity_id}.jsonl
    logs/session_{id}/combat/summary.jsonl
    logs/session_{id}/actions/all.jsonl
    logs/session_{id}/actions/failed.jsonl
"""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import structlog


class FileDispatchProcessor:
    """Writes log entries to multiple JSONL files based on domain and context.

    Sits in the structlog processor chain before the renderer.
    Writes its own JSON (independent of renderer output), then passes
    event_dict through unchanged so the console renderer still fires.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def __call__(
        self,
        logger: structlog.types.WrappedLogger,
        method_name: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        session_id = event_dict.get("session_id", "unknown")
        session_dir = self._base / f"session_{session_id}"

        domain = str(event_dict.get("domain", ""))
        entity_id = event_dict.get("entity_id")
        event = str(event_dict.get("event", ""))

        # LLM full context → separate JSON file, not JSONL
        if domain == "llm.context":
            self._write_llm_context(session_dir, event_dict, entity_id)
            return event_dict

        json_line = json.dumps(event_dict, default=str, ensure_ascii=False) + "\n"

        targets: list[Path] = [session_dir / "full.jsonl"]

        if domain.startswith("llm"):
            targets.append(session_dir / "llm" / "all.jsonl")
            if entity_id:
                targets.append(session_dir / "llm" / f"{entity_id}.jsonl")

        if entity_id:
            targets.append(session_dir / "entities" / f"{entity_id}.jsonl")

        if domain == "combat" and event in ("combat_start", "combat_end"):
            targets.append(session_dir / "combat" / "summary.jsonl")

        if domain == "action":
            targets.append(session_dir / "actions" / "all.jsonl")
            if event_dict.get("success") is False:
                targets.append(session_dir / "actions" / "failed.jsonl")

        if domain == "round":
            targets.append(session_dir / "round" / "all.jsonl")

        for path in targets:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json_line)

        return event_dict

    @staticmethod
    def _write_llm_context(
        session_dir: Path,
        event_dict: MutableMapping[str, Any],
        entity_id: object,
    ) -> None:
        """Write full LLM prompt + response as a separate JSON file."""
        entity = str(entity_id) if entity_id else "unknown"
        ts = str(event_dict.get("timestamp", ""))
        # Use timestamp for uniqueness: "2026-03-24T10:43:08.154Z" → "10-43-08"
        time_part = ts[11:19].replace(":", "-") if len(ts) > 19 else "unknown"
        filename = f"{entity}_{time_part}.json"
        path = session_dir / "llm" / "contexts" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(event_dict, f, default=str, ensure_ascii=False, indent=2)
