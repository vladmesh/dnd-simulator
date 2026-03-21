"""Tests for the NPC memory summarizer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from dnd_simulator.layers.entities.models import NpcMemory
from dnd_simulator.llm.summarizer import RECENT_LIMIT, MemorySummarizer


def _mock_llm(response_json: dict[str, object]) -> MagicMock:
    """Create a mock LlmClient that returns a JSON string."""
    llm = MagicMock()
    llm.generate.return_value = json.dumps(response_json, ensure_ascii=False)
    return llm


class TestMemorySummarizer:
    def test_conversation_ended_merges_into_recent(self) -> None:
        memory = NpcMemory(
            tags=["angry"],
            recent="Met a stranger yesterday.",
            current_conversation="Discussed iron prices with the traveler.",
        )
        llm = _mock_llm(
            {
                "tags": ["angry"],
                "recent": "Met a stranger yesterday. Discussed iron prices with a traveler.",
                "inner_state": "thinking about iron supply",
                "current_conversation": "",
            }
        )
        summarizer = MemorySummarizer(llm)
        result = summarizer.summarize(memory, [], "conversation_ended")

        assert result.current_conversation == ""
        assert "iron" in result.recent
        assert result.inner_state == "thinking about iron supply"
        # Tags preserved from original, not from LLM response
        assert result.tags == ["angry"]

    def test_combat_ended_adds_to_recent(self) -> None:
        memory = NpcMemory(tags=["hates:orcs"], recent="")
        events = ["Orc attacks you for 5 damage.", "You attack Orc for 8 damage.", "Orc dies."]
        llm = _mock_llm(
            {
                "tags": ["hates:orcs"],
                "recent": "Killed an orc in combat.",
                "inner_state": "satisfied",
                "current_conversation": "",
            }
        )
        summarizer = MemorySummarizer(llm)
        result = summarizer.summarize(memory, events, "combat_ended")

        assert "orc" in result.recent.lower()
        assert result.tags == ["hates:orcs"]

    def test_tags_preserved_even_if_llm_changes_them(self) -> None:
        memory = NpcMemory(tags=["angry", "hates:player"])
        llm = _mock_llm(
            {
                "tags": ["happy"],  # LLM tries to change tags — should be ignored
                "recent": "Something happened.",
                "inner_state": "",
                "current_conversation": "",
            }
        )
        summarizer = MemorySummarizer(llm)
        result = summarizer.summarize(memory, ["Event."], "combat_ended")
        assert result.tags == ["angry", "hates:player"]

    def test_no_events_returns_original(self) -> None:
        memory = NpcMemory(recent="Old stuff.")
        llm = MagicMock()
        summarizer = MemorySummarizer(llm)
        result = summarizer.summarize(memory, [], "combat_ended")
        assert result is memory
        llm.generate.assert_not_called()

    def test_malformed_response_returns_original(self) -> None:
        memory = NpcMemory(recent="Old stuff.")
        llm = MagicMock()
        llm.generate.return_value = "This is not JSON at all!"
        summarizer = MemorySummarizer(llm)
        result = summarizer.summarize(memory, ["Event."], "combat_ended")
        assert result is memory

    def test_markdown_code_fence_stripped(self) -> None:
        memory = NpcMemory(tags=[])
        response = (
            '```json\n{"tags": [], "recent": "Fought a wolf.", "inner_state": "", "current_conversation": ""}\n```'
        )
        llm = MagicMock()
        llm.generate.return_value = response
        summarizer = MemorySummarizer(llm)
        result = summarizer.summarize(memory, ["Wolf attacks."], "combat_ended")
        assert result.recent == "Fought a wolf."

    def test_needs_compression(self) -> None:
        summarizer = MemorySummarizer(MagicMock())
        short = NpcMemory(recent="Short.")
        long = NpcMemory(recent="x" * (RECENT_LIMIT + 1))
        assert summarizer.needs_compression(short) is False
        assert summarizer.needs_compression(long) is True
