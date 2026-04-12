"""BrainFactory — single point for creating Brain instances from BrainType."""

from __future__ import annotations

import structlog

from dnd_simulator.core.brain import Brain, BrainType
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.rules.rule_brain import RuleBrain

logger = structlog.get_logger(domain="brain")


class BrainFactory:
    """Creates Brain instances. Knows about all brain types so callers don't have to."""

    def __init__(self, llm: LlmClient | None = None) -> None:
        self._llm = llm

    def create(self, ai_type: BrainType, *, strict: bool = False) -> Brain:
        """Create a Brain for the given BrainType.

        Args:
            ai_type: BrainType enum value.
            strict: if True, raise on missing LLM. If False, fall back to RuleBrain.
                    Use strict=True for explicit user requests (API), False for world loading.
        """
        match ai_type:
            case BrainType.RULE_BASED:
                return RuleBrain()
            case BrainType.LLM:
                if self._llm is None:
                    if strict:
                        raise ValueError("LLM not configured")
                    logger.warning("llm_not_configured_fallback", ai_type=ai_type.value)
                    return RuleBrain()
                from dnd_simulator.llm.brain import LlmBrain

                return LlmBrain(self._llm)
