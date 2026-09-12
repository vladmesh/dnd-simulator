"""Memory summarizer — compresses NPC events into their inner journal."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.inner_self import InnerSelf

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
- If trigger is "conversation_ended": merge current_conversation into journal, clear current_conversation
- If trigger is "combat_ended": add combat outcome to journal
- If trigger is "journal_overflow": compress journal to be shorter while keeping key facts
- Keep journal under 300 characters
- Do NOT modify relations, mood, goals, alignment, or thoughts
- Return ONLY valid JSON, no explanation

Return the updated inner-self object with keys: relations, mood, goals, alignment,
journal, thoughts, current_conversation"""

# Character limit for journal before triggering overflow compression
JOURNAL_LIMIT = 300


class MemorySummarizer:
    """Compresses NPC events into structured memory via a cheap LLM call."""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def summarize(self, inner_self: InnerSelf, new_events: list[str], trigger: str) -> InnerSelf:
        """Compress events into the free journal. Typed state is preserved."""
        if not new_events and trigger not in ("journal_overflow", "conversation_ended"):
            return inner_self

        events_text = "\n".join(f"- {e}" for e in new_events) if new_events else "(no new events)"
        memory_json = json.dumps(inner_self.to_dict(), ensure_ascii=False, indent=2)

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
            result = InnerSelf.from_dict(data)
            result.relations = list(inner_self.relations)
            result.mood = inner_self.mood
            result.goals = list(inner_self.goals)
            result.alignment = inner_self.alignment
            result.thoughts = list(inner_self.thoughts)
            return result
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("summarizer_parse_failed")
            return inner_self

    def needs_compression(self, inner_self: InnerSelf) -> bool:
        """Check if the journal exceeds the size limit."""
        return len(inner_self.journal) > JOURNAL_LIMIT
