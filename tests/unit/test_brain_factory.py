"""Tests for BrainFactory — all 5 branches."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.brain import RuleBrain
from dnd_simulator.llm.brain import LlmBrain
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.service.brain_factory import BrainFactory


class TestBrainFactory:
    """BrainFactory creates Brain instances from ai_type strings."""

    def test_rule_based_returns_rule_brain(self) -> None:
        factory = BrainFactory(llm=None)
        brain = factory.create("rule_based")
        assert isinstance(brain, RuleBrain)

    def test_llm_with_client_returns_llm_brain(self) -> None:
        mock_llm = MagicMock(spec=LlmClient)
        factory = BrainFactory(llm=mock_llm)
        brain = factory.create("llm")
        assert isinstance(brain, LlmBrain)

    def test_llm_strict_without_client_raises(self) -> None:
        factory = BrainFactory(llm=None)
        with pytest.raises(ValueError, match="LLM not configured"):
            factory.create("llm", strict=True)

    def test_llm_non_strict_without_client_falls_back_to_rule_brain(self) -> None:
        factory = BrainFactory(llm=None)
        brain = factory.create("llm", strict=False)
        assert isinstance(brain, RuleBrain)

    def test_unknown_ai_type_raises(self) -> None:
        factory = BrainFactory(llm=None)
        with pytest.raises(ValueError, match="Unknown ai_type: telepathy"):
            factory.create("telepathy")
