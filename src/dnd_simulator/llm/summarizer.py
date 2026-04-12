"""Memory summarizer — compresses NPC events into structured memory."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.npc_memory import NpcMemory

if TYPE_CHECKING:
    from dnd_simulator.llm.client import LlmClient

logger = structlog.get_logger(domain="llm.summarizer")

_SUMMARIZE_PROMPT = """\
You are a memory compressor for an NPC in a fantasy RPG.

The NPC's current memory is:
{memory_json}

New events that happened (trigger: {trigger}):
{events}

Update the memory JSON. Rules:
- If trigger is "conversation_ended": merge current_conversation into recent, clear current_conversation
- If trigger is "combat_ended": add combat outcome to recent
- If trigger is "recent_overflow": compress recent to be shorter while keeping key facts
- Keep recent under 300 characters
- Update inner_state to reflect how the NPC feels now
- Do NOT modify tags (those are managed separately)
- Return ONLY valid JSON, no explanation

Return the updated memory object with keys: tags, recent, inner_state, current_conversation"""

# Character limit for 'recent' before triggering overflow compression
RECENT_LIMIT = 300


class MemorySummarizer:
    """Compresses NPC events into structured memory via a cheap LLM call."""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def summarize(self, memory: NpcMemory, new_events: list[str], trigger: str) -> NpcMemory:
        """Compress events into memory. Returns updated NpcMemory."""
        if not new_events and trigger not in ("recent_overflow", "conversation_ended"):
            return memory

        events_text = "\n".join(f"- {e}" for e in new_events) if new_events else "(no new events)"
        memory_json = json.dumps(memory.to_dict(), ensure_ascii=False, indent=2)

        prompt = _SUMMARIZE_PROMPT.format(
            memory_json=memory_json,
            trigger=trigger,
            events=events_text,
        )

        messages: list[dict[str, object]] = [
            {"role": "user", "content": prompt},
        ]

        response_text = self._llm.generate(messages, max_tokens=400, temperature=0.3)

        try:
            # Strip markdown code fences if present
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            data = json.loads(cleaned)
            # Preserve original tags (summarizer must not modify them)
            result = NpcMemory.from_dict(data)
            result.tags = list(memory.tags)
            return result
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("summarizer_parse_failed")
            return memory

    def needs_compression(self, memory: NpcMemory) -> bool:
        """Check if recent memory exceeds the size limit."""
        return len(memory.recent) > RECENT_LIMIT
