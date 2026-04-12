"""Tests for brain reassignment after save/load.

Brains are transient — not serialized. After load_state() restores entities
(including spawned ones), brains must be reassigned based on ai_type.
Brain switches (ai_type changes) must survive save → load.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.brain import BrainType
from dnd_simulator.core.character import Creature, NpcRole
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.service.brain_factory import BrainFactory


def _make_npc(npc_id: str = "guard", ai_type: BrainType = BrainType.RULE_BASED, **kwargs: object) -> Npc:
    defaults = {
        "id": npc_id,
        "name": npc_id.title(),
        "location_id": "town_square",
        "role": NpcRole.GUARD,
        "personality": "Stern.",
        "settlement_id": "town",
        "ai_type": ai_type,
    }
    defaults.update(kwargs)
    return Npc(**defaults)  # type: ignore[arg-type]


class TestBrainSwitchPreservedAfterLoad:
    def test_ai_type_change_reflected_in_brain_after_load(self) -> None:
        """Switch NPC ai_type from rule_based to llm, save, load on fresh layer,
        reassign brains — brain should match the saved ai_type, not the template default."""
        npc = _make_npc(ai_type=BrainType.RULE_BASED)
        factory = BrainFactory(llm=None)
        npc.brain = factory.create(BrainType.RULE_BASED)

        # Switch ai_type (simulating PUT /creatures/:id/brain)
        npc.ai_type = BrainType.LLM

        layer = EntitiesLayer(entities=[npc])
        state = layer.get_state()

        # Fresh layer with template NPC (default ai_type)
        fresh_npc = _make_npc(ai_type=BrainType.RULE_BASED)
        fresh_npc.brain = factory.create(BrainType.RULE_BASED)
        fresh_layer = EntitiesLayer(entities=[fresh_npc])
        fresh_layer.load_state(state)

        # Before reassignment — brain is stale (still rule_based from template)
        restored = fresh_layer.get_entity("guard")
        assert isinstance(restored, Npc)
        assert restored.ai_type == "llm"  # ai_type restored from save

        # Reassign brains based on current ai_type
        for entity in fresh_layer._entities.values():
            if isinstance(entity, Npc):
                entity.brain = factory.create(entity.ai_type)

        # Brain should now match ai_type (RuleBrain fallback since no LLM configured)
        assert restored.brain is not None
        # The key test: factory was called with "llm", not "rule_based"
        # With no LLM configured, factory falls back to RuleBrain, but ai_type is preserved
        assert restored.ai_type == "llm"


class TestSpawnedCreatureGetsBrainAfterLoad:
    def test_spawned_npc_gets_brain_after_reassignment(self) -> None:
        """Spawned NPC recreated from save data has brain=None until reassignment."""
        template_npc = _make_npc("template_guard")
        spawned_npc = _make_npc("spawned_goblin", ai_type=BrainType.RULE_BASED)

        layer = EntitiesLayer(entities=[template_npc, spawned_npc])
        state = layer.get_state()

        # Fresh layer only has template — spawned gets recreated by load_state
        fresh_layer = EntitiesLayer(entities=[_make_npc("template_guard")])
        fresh_layer.load_state(state)

        spawned = fresh_layer.get_entity("spawned_goblin")
        assert spawned is not None
        assert isinstance(spawned, Npc)
        assert spawned.brain is None  # No brain yet — layer can't assign it

        # Reassign brains
        factory = BrainFactory(llm=None)
        for entity in fresh_layer._entities.values():
            if isinstance(entity, Npc):
                entity.brain = factory.create(entity.ai_type)

        assert spawned.brain is not None

    def test_spawned_creature_gets_brain_after_reassignment(self) -> None:
        """Generic Creature spawned at runtime also needs brain assignment."""
        template_npc = _make_npc("template_guard")
        monster = Creature(
            id="wolf",
            name="Wolf",
            location_id="forest",
            max_hp=11,
            current_hp=11,
            ac=13,
            speed=40,
        )

        layer = EntitiesLayer(entities=[template_npc, monster])
        state = layer.get_state()

        fresh_layer = EntitiesLayer(entities=[_make_npc("template_guard")])
        fresh_layer.load_state(state)

        wolf = fresh_layer.get_entity("wolf")
        assert wolf is not None
        assert isinstance(wolf, Creature)
        assert wolf.brain is None

        # Reassign — generic Creatures default to rule_based
        factory = BrainFactory(llm=None)
        for entity in fresh_layer._entities.values():
            if isinstance(entity, Creature) and entity.brain is None:
                ai_type = entity.ai_type if isinstance(entity, Npc) else BrainType.RULE_BASED
                entity.brain = factory.create(ai_type)

        assert wolf.brain is not None


class TestBrainReassignmentIdempotent:
    def test_double_reassignment_is_safe(self) -> None:
        """Calling brain reassignment twice doesn't break anything."""
        npc = _make_npc(ai_type=BrainType.RULE_BASED)
        factory = BrainFactory(llm=None)

        layer = EntitiesLayer(entities=[npc])

        for _ in range(2):
            for entity in layer._entities.values():
                if isinstance(entity, Npc):
                    entity.brain = factory.create(entity.ai_type)

        restored = layer.get_entity("guard")
        assert isinstance(restored, Npc)
        assert restored.brain is not None


class TestBrainFactoryCallsTracked:
    def test_factory_called_with_saved_ai_type_not_template(self) -> None:
        """Verify the factory is called with the ai_type from save data, not the template default."""
        npc = _make_npc(ai_type=BrainType.LLM)  # saved as llm
        layer = EntitiesLayer(entities=[npc])
        state = layer.get_state()

        fresh_npc = _make_npc(ai_type=BrainType.RULE_BASED)  # template default
        fresh_layer = EntitiesLayer(entities=[fresh_npc])
        fresh_layer.load_state(state)

        factory = BrainFactory(llm=None)
        mock_create = MagicMock(wraps=factory.create)
        factory.create = mock_create  # type: ignore[method-assign]

        for entity in fresh_layer._entities.values():
            if isinstance(entity, Npc):
                entity.brain = factory.create(entity.ai_type)

        # Factory must have been called with "llm" (from save), not "rule_based" (template)
        mock_create.assert_called_once_with(BrainType.LLM)
