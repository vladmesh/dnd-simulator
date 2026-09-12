"""Tests for the inner-self journal summarizer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from dnd_simulator.core.inner_self import InnerSelf, Mood, Relationship, RelationshipType
from dnd_simulator.llm.summarizer import JOURNAL_LIMIT, MemorySummarizer


def _mock_llm(response_json: dict[str, object]) -> MagicMock:
    llm = MagicMock()
    llm.generate.return_value = json.dumps(response_json, ensure_ascii=False)
    return llm


class TestMemorySummarizer:
    def test_conversation_ended_updates_journal_and_preserves_core(self) -> None:
        inner_self = InnerSelf(
            mood=Mood.ANGRY,
            relations=[Relationship("orc", RelationshipType.HATES)],
            journal="Met a stranger yesterday.",
            current_conversation="Discussed iron prices with the traveler.",
        )
        llm = _mock_llm(
            {
                "relations": [],
                "mood": "happy",
                "goals": [],
                "alignment": {"law_chaos": 0, "good_evil": 0},
                "journal": "Met a stranger yesterday. Discussed iron prices with a traveler.",
                "thoughts": [],
                "current_conversation": "",
            }
        )
        result = MemorySummarizer(llm).summarize(inner_self, [], "conversation_ended")

        assert result.current_conversation == ""
        assert "iron" in result.journal
        assert result.mood is Mood.ANGRY
        assert result.relations == inner_self.relations

    def test_no_events_and_malformed_response_return_original(self) -> None:
        inner_self = InnerSelf(journal="Old stuff.")
        llm = MagicMock()
        summarizer = MemorySummarizer(llm)
        assert summarizer.summarize(inner_self, [], "combat_ended") is inner_self
        llm.generate.return_value = "not JSON"
        assert summarizer.summarize(inner_self, ["Event."], "combat_ended") is inner_self

    def test_markdown_code_fence_stripped(self) -> None:
        inner_self = InnerSelf()
        llm = MagicMock()
        llm.generate.return_value = (
            '```json\n{"relations": [], "mood": "neutral", "goals": [], '
            '"alignment": {"law_chaos": 0, "good_evil": 0}, "journal": "Fought a wolf.", '
            '"thoughts": [], "current_conversation": ""}\n```'
        )
        result = MemorySummarizer(llm).summarize(inner_self, ["Wolf attacks."], "combat_ended")
        assert result.journal == "Fought a wolf."

    def test_needs_compression(self) -> None:
        summarizer = MemorySummarizer(MagicMock())
        assert summarizer.needs_compression(InnerSelf(journal="Short.")) is False
        assert summarizer.needs_compression(InnerSelf(journal="x" * (JOURNAL_LIMIT + 1))) is True
