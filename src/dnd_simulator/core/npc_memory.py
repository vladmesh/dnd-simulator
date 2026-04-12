"""Structured NPC memory — pure domain data, no layer dependencies.

Lives in core/ so llm/ can use it without reaching into layers/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NpcMemory:
    """Structured memory for an NPC — readable by both LLM and RuleBrain.

    Fields:
        tags: structured emotional/relational tags (e.g. "angry", "hates:orc_chief")
        recent: summarized recent events
        inner_state: current emotional/mental state
        current_conversation: summary of ongoing conversation
    """

    tags: list[str] = field(default_factory=list)
    recent: str = ""
    inner_state: str = ""
    current_conversation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tags": list(self.tags),
            "recent": self.recent,
            "inner_state": self.inner_state,
            "current_conversation": self.current_conversation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NpcMemory:
        return cls(
            tags=list(data.get("tags", [])),
            recent=str(data.get("recent", "")),
            inner_state=str(data.get("inner_state", "")),
            current_conversation=str(data.get("current_conversation", "")),
        )
