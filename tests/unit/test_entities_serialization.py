"""Tests for entities layer serialization — resource pools and NPC ai_type round-trip."""

from dnd_simulator.core.character import NpcRole
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc


def _make_fighter_npc(**kwargs: object) -> Npc:
    """Create an NPC with a Second Wind resource pool."""
    defaults = {
        "id": "fighter_npc",
        "name": "Sir Reginald",
        "location_id": "town_square",
        "role": NpcRole.GUARD,
        "personality": "Brave.",
        "settlement_id": "town",
    }
    defaults.update(kwargs)
    npc = Npc(**defaults)  # type: ignore[arg-type]
    npc.resource_pools = [
        ResourcePool(id="second_wind", max_uses=1, current_uses=1, reset_on=RestType.SHORT_REST),
    ]
    return npc


class TestResourcePoolRoundTrip:
    def test_spent_resource_survives_save_load(self) -> None:
        """Second Wind with current_uses=0 stays 0 after save/load."""
        npc = _make_fighter_npc()
        # Spend the resource
        npc.resource_pools[0].current_uses = 0

        layer = EntitiesLayer(entities=[npc])
        state = layer.get_state()

        # Restore into a fresh layer with a fresh NPC (pools at max)
        fresh_npc = _make_fighter_npc()
        assert fresh_npc.resource_pools[0].current_uses == 1  # starts at max

        fresh_layer = EntitiesLayer(entities=[fresh_npc])
        fresh_layer.load_state(state)

        restored = fresh_layer.get_entity("fighter_npc")
        assert isinstance(restored, Npc)
        assert len(restored.resource_pools) == 1
        assert restored.resource_pools[0].id == "second_wind"
        assert restored.resource_pools[0].current_uses == 0

    def test_multiple_pools_preserved(self) -> None:
        """Two pools at different states survive save/load."""
        npc = _make_fighter_npc()
        npc.resource_pools = [
            ResourcePool(id="second_wind", max_uses=1, current_uses=0, reset_on=RestType.SHORT_REST),
            ResourcePool(id="action_surge", max_uses=2, current_uses=1, reset_on=RestType.SHORT_REST),
        ]

        layer = EntitiesLayer(entities=[npc])
        state = layer.get_state()

        fresh_npc = _make_fighter_npc()
        fresh_npc.resource_pools = [
            ResourcePool(id="second_wind", max_uses=1, current_uses=1, reset_on=RestType.SHORT_REST),
            ResourcePool(id="action_surge", max_uses=2, current_uses=2, reset_on=RestType.SHORT_REST),
        ]
        fresh_layer = EntitiesLayer(entities=[fresh_npc])
        fresh_layer.load_state(state)

        restored = fresh_layer.get_entity("fighter_npc")
        assert isinstance(restored, Npc)
        pools = {p.id: p for p in restored.resource_pools}
        assert pools["second_wind"].current_uses == 0
        assert pools["action_surge"].current_uses == 1
        assert pools["action_surge"].max_uses == 2


class TestNpcAiTypeRoundTrip:
    def test_llm_ai_type_survives_save_load(self) -> None:
        """NPC with ai_type='llm' keeps it after save/load."""
        npc = Npc(
            id="wizard",
            name="Gandalf",
            location_id="tower",
            role=NpcRole.COMMONER,
            personality="Mysterious.",
            settlement_id="town",
            ai_type="llm",
        )

        layer = EntitiesLayer(entities=[npc])
        state = layer.get_state()

        fresh_npc = Npc(
            id="wizard",
            name="Gandalf",
            location_id="tower",
            role=NpcRole.COMMONER,
            personality="Mysterious.",
            settlement_id="town",
            ai_type="rule_based",  # default
        )
        fresh_layer = EntitiesLayer(entities=[fresh_npc])
        fresh_layer.load_state(state)

        restored = fresh_layer.get_entity("wizard")
        assert isinstance(restored, Npc)
        assert restored.ai_type == "llm"
