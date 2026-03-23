"""BrainFactory — single point for creating Brain instances from ai_type strings."""

from __future__ import annotations

import logging

from dnd_simulator.core.brain import Brain, RuleBrain
from dnd_simulator.llm.client import LlmClient

logger = logging.getLogger("dnd_simulator.brain_factory")


class BrainFactory:
    """Creates Brain instances. Knows about all brain types so callers don't have to."""

    def __init__(self, llm: LlmClient | None = None) -> None:
        self._llm = llm

    def create(self, ai_type: str, *, strict: bool = False) -> Brain:
        """Create a Brain for the given ai_type.

        Args:
            ai_type: "rule_based" or "llm".
            strict: if True, raise on missing LLM. If False, fall back to RuleBrain.
                    Use strict=True for explicit user requests (API), False for world loading.
        """
        if ai_type == "rule_based":
            return RuleBrain()
        if ai_type == "llm":
            if self._llm is None:
                if strict:
                    raise ValueError("LLM not configured")
                logger.warning("LLM not configured — falling back to RuleBrain for ai_type='llm'")
                return RuleBrain()
            from dnd_simulator.llm.brain import LlmBrain

            return LlmBrain(self._llm)
        raise ValueError(f"Unknown ai_type: {ai_type}")
