"""Tests for BrainFactory — enum-typed ai_type dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.brain import BrainType
from dnd_simulator.llm.brain import LlmBrain
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.rules.rule_brain import RuleBrain
from dnd_simulator.service.brain_factory import BrainFactory


class TestBrainFactory:
    """BrainFactory creates Brain instances from BrainType values."""

    def test_rule_based_returns_rule_brain(self) -> None:
        factory = BrainFactory(llm=None)
        brain = factory.create(BrainType.RULE_BASED)
        assert isinstance(brain, RuleBrain)

    def test_llm_with_client_returns_llm_brain(self) -> None:
        mock_llm = MagicMock(spec=LlmClient)
        factory = BrainFactory(llm=mock_llm)
        brain = factory.create(BrainType.LLM)
        assert isinstance(brain, LlmBrain)

    def test_llm_strict_without_client_raises(self) -> None:
        factory = BrainFactory(llm=None)
        with pytest.raises(ValueError, match="LLM not configured"):
            factory.create(BrainType.LLM, strict=True)

    def test_llm_non_strict_without_client_falls_back_to_rule_brain(self) -> None:
        factory = BrainFactory(llm=None)
        brain = factory.create(BrainType.LLM, strict=False)
        assert isinstance(brain, RuleBrain)

    def test_unknown_ai_type_raises_at_enum_construction(self) -> None:
        """Unknown ai_type is rejected by the enum, not the factory."""
        with pytest.raises(ValueError):
            BrainType("telepathy")


class TestBrainTypeParseFailFast:
    """Unknown ai value in YAML-shaped data fails at parse time, not at brain creation."""

    def test_unknown_ai_in_npc_content_raises(self) -> None:
        from pydantic import ValidationError

        from dnd_simulator.content_loader.schemas import NpcContent

        with pytest.raises(ValidationError):
            NpcContent.model_validate({"name": {"en": "Weird"}, "ai": "telepathy"})
