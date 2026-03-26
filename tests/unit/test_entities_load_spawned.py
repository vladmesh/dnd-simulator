"""Tests for recreating spawned entities from save data.

Spawned creatures (added via master API at runtime) must survive save/load:
get_state() includes entity_type discriminator, load_state() recreates missing entities.
"""

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Creature,
    DamageComponent,
    DamageType,
    NpcRole,
)
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc, NpcMemory


def _template_npc() -> Npc:
    """An NPC that exists in the world template (always present in fresh layer)."""
    return Npc(
        id="olga",
        name="Olga",
        location_id="tavern",
        role=NpcRole.TAVERN_KEEPER,
        personality="Cheerful.",
        settlement_id="village",
    )


class TestSpawnedNpcRoundTrip:
    def test_spawned_npc_recreated_on_load(self) -> None:
        """NPC spawned at runtime survives save → load on a fresh layer."""
        template_npc = _template_npc()
        spawned_npc = Npc(
            id="goblin_chief",
            name="Grak",
            location_id="forest",
            role=NpcRole.GUARD,
            personality="Aggressive and cunning.",
            settlement_id="goblin_camp",
            ai_type="rule_based",
            max_hp=30,
            current_hp=22,
            ac=15,
            speed=30,
        )
        spawned_npc.memory = NpcMemory(
            tags=["hostile", "leader"],
            recent="Fought adventurers.",
            inner_state="Wary.",
        )

        layer = EntitiesLayer(entities=[template_npc, spawned_npc])
        state = layer.get_state()

        # Fresh layer only has the template NPC — spawned NPC is "missing"
        fresh_layer = EntitiesLayer(entities=[_template_npc()])
        fresh_layer.load_state(state)

        restored = fresh_layer.get_entity("goblin_chief")
        assert restored is not None, "Spawned NPC should be recreated from save data"
        assert isinstance(restored, Npc)
        assert restored.name == "Grak"
        assert restored.location_id == "forest"
        assert restored.role == NpcRole.GUARD
        assert restored.personality == "Aggressive and cunning."
        assert restored.settlement_id == "goblin_camp"
        assert restored.ai_type == "rule_based"
        assert restored.current_hp == 22
        assert restored.memory.tags == ["hostile", "leader"]
        assert restored.memory.recent == "Fought adventurers."
        assert restored.memory.inner_state == "Wary."


class TestSpawnedCreatureRoundTrip:
    def test_spawned_creature_recreated_on_load(self) -> None:
        """Generic creature (monster) spawned at runtime survives save → load."""
        template_npc = _template_npc()
        monster = Creature(
            id="dire_wolf",
            name="Dire Wolf",
            location_id="forest",
            max_hp=37,
            current_hp=25,
            ac=14,
            speed=50,
            ability_scores=AbilityScores.from_dict({"str": 17, "dex": 15, "con": 15, "int": 3, "wis": 12, "cha": 7}),
            attacks=(
                Attack(
                    name="bite",
                    ability=Ability.STR,
                    damage=(DamageComponent(dice="2d6", type=DamageType.PIERCING),),
                    reach=5,
                ),
            ),
        )

        layer = EntitiesLayer(entities=[template_npc, monster])
        state = layer.get_state()

        fresh_layer = EntitiesLayer(entities=[_template_npc()])
        fresh_layer.load_state(state)

        restored = fresh_layer.get_entity("dire_wolf")
        assert restored is not None, "Spawned creature should be recreated from save data"
        assert isinstance(restored, Creature)
        assert not isinstance(restored, Npc)
        assert restored.name == "Dire Wolf"
        assert restored.location_id == "forest"
        assert restored.max_hp == 37
        assert restored.current_hp == 25
        assert restored.ac == 14
        assert restored.speed == 50
        assert restored.ability_scores[Ability.STR] == 17
        assert restored.ability_scores[Ability.DEX] == 15
        assert len(restored.attacks) == 1
        assert restored.attacks[0].name == "bite"
        assert restored.attacks[0].damage[0].dice == "2d6"


class TestSpawnedEntityWithConditionsAndInventory:
    def test_spawned_npc_with_conditions_and_inventory(self) -> None:
        """Spawned NPC with conditions and inventory items preserves them through save/load."""
        template_npc = _template_npc()
        spawned = Npc(
            id="poisoned_guard",
            name="Wounded Guard",
            location_id="gate",
            role=NpcRole.GUARD,
            personality="In pain.",
            settlement_id="village",
            max_hp=20,
            current_hp=8,
        )
        spawned.conditions = {Condition.POISONED: 3, Condition.PRONE: None}
        spawned.inventory = [
            Item(id="health_potion", name="Health Potion", item_type=ItemType.POTION),
            Item(id="short_sword", name="Short Sword", item_type=ItemType.WEAPON),
        ]
        spawned.resource_pools = [
            ResourcePool(id="second_wind", max_uses=1, current_uses=0, reset_on=RestType.SHORT_REST),
        ]

        layer = EntitiesLayer(entities=[template_npc, spawned])
        state = layer.get_state()

        fresh_layer = EntitiesLayer(entities=[_template_npc()])
        fresh_layer.load_state(state)

        restored = fresh_layer.get_entity("poisoned_guard")
        assert restored is not None
        assert isinstance(restored, Npc)

        # Conditions preserved
        assert Condition.POISONED in restored.conditions
        assert restored.conditions[Condition.POISONED] == 3
        assert Condition.PRONE in restored.conditions
        assert restored.conditions[Condition.PRONE] is None  # permanent

        # Inventory preserved
        assert len(restored.inventory) == 2
        inv_ids = {item.id for item in restored.inventory}
        assert "health_potion" in inv_ids
        assert "short_sword" in inv_ids

        # Resource pools preserved
        assert len(restored.resource_pools) == 1
        assert restored.resource_pools[0].id == "second_wind"
        assert restored.resource_pools[0].current_uses == 0
