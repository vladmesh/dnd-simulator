"""Tests for entities layer serialization — resource pools, NPC ai_type, and combat state round-trip."""

from dnd_simulator.core.character import Creature, NpcRole
from dnd_simulator.core.combat import BattleMap, CombatState, Position, Wall
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


def _make_creature(id: str, location_id: str = "arena") -> Creature:
    return Creature(id=id, name=id.title(), location_id=location_id)


class TestCombatStateRoundTrip:
    def test_no_combats_round_trip(self) -> None:
        """No active combats — save/load stays empty."""
        c = _make_creature("warrior")
        layer = EntitiesLayer(entities=[c])
        state = layer.get_state()

        fresh = EntitiesLayer(entities=[_make_creature("warrior")])
        fresh.load_state(state)
        assert fresh.get_combat("arena") is None

    def test_mid_combat_round_trip(self) -> None:
        """Combat at round 3 with positions survives save/load."""
        c1 = _make_creature("fighter")
        c2 = _make_creature("goblin")
        c1.in_combat = True
        c2.in_combat = True

        layer = EntitiesLayer(entities=[c1, c2])

        # Manually inject combat state (bypassing start_combat to control positions)
        bm = BattleMap(width=60, height=60)
        bm.set_position("fighter", Position(10, 15))
        bm.set_position("goblin", Position(30, 25))
        combat = CombatState(
            location_id="arena",
            turn_order=["fighter", "goblin"],
            round_number=3,
            rounds_without_attack=1,
            battle_map=bm,
        )
        layer._combat._combats["arena"] = combat

        state = layer.get_state()

        # Restore
        fresh_c1 = _make_creature("fighter")
        fresh_c2 = _make_creature("goblin")
        fresh_layer = EntitiesLayer(entities=[fresh_c1, fresh_c2])
        fresh_layer.load_state(state)

        restored_combat = fresh_layer.get_combat("arena")
        assert restored_combat is not None
        assert restored_combat.turn_order == ["fighter", "goblin"]
        assert restored_combat.round_number == 3
        assert restored_combat.rounds_without_attack == 1
        assert restored_combat.battle_map.get_position("fighter") == Position(10, 15)
        assert restored_combat.battle_map.get_position("goblin") == Position(30, 25)
        assert restored_combat.battle_map.width == 60
        assert restored_combat.battle_map.height == 60

    def test_battle_map_walls_preserved(self) -> None:
        """Inner walls survive round-trip and still block movement."""
        c1 = _make_creature("a")
        c2 = _make_creature("b")
        c1.in_combat = True
        c2.in_combat = True

        inner_wall = Wall(x1=20, y1=0, x2=20, y2=30)
        bm = BattleMap(width=40, height=40, walls=[inner_wall])
        bm.set_position("a", Position(15, 10))
        bm.set_position("b", Position(25, 10))

        layer = EntitiesLayer(entities=[c1, c2])
        combat = CombatState(
            location_id="arena",
            turn_order=["a", "b"],
            battle_map=bm,
        )
        layer._combat._combats["arena"] = combat

        # Verify the wall blocks before save
        assert bm.is_step_blocked(Position(15, 10), Position(20, 10))

        state = layer.get_state()

        fresh_layer = EntitiesLayer(entities=[_make_creature("a"), _make_creature("b")])
        fresh_layer.load_state(state)

        restored = fresh_layer.get_combat("arena")
        assert restored is not None
        # Same wall still blocks the same step
        assert restored.battle_map.is_step_blocked(Position(15, 10), Position(20, 10))
        # Non-walled step is not blocked
        assert not restored.battle_map.is_step_blocked(Position(5, 10), Position(10, 10))

    def test_multiple_simultaneous_combats(self) -> None:
        """Two combats at different locations survive independently."""
        c1 = _make_creature("a", location_id="loc1")
        c2 = _make_creature("b", location_id="loc1")
        c3 = _make_creature("c", location_id="loc2")
        c4 = _make_creature("d", location_id="loc2")
        for c in (c1, c2, c3, c4):
            c.in_combat = True

        layer = EntitiesLayer(entities=[c1, c2, c3, c4])

        bm1 = BattleMap(width=40, height=40)
        bm1.set_position("a", Position(5, 5))
        bm1.set_position("b", Position(20, 20))
        combat1 = CombatState(location_id="loc1", turn_order=["a", "b"], round_number=2, battle_map=bm1)

        bm2 = BattleMap(width=80, height=80)
        bm2.set_position("c", Position(10, 10))
        bm2.set_position("d", Position(60, 60))
        combat2 = CombatState(location_id="loc2", turn_order=["d", "c"], round_number=5, battle_map=bm2)

        layer._combat._combats["loc1"] = combat1
        layer._combat._combats["loc2"] = combat2

        state = layer.get_state()

        fresh_layer = EntitiesLayer(
            entities=[
                _make_creature("a", "loc1"),
                _make_creature("b", "loc1"),
                _make_creature("c", "loc2"),
                _make_creature("d", "loc2"),
            ]
        )
        fresh_layer.load_state(state)

        r1 = fresh_layer.get_combat("loc1")
        r2 = fresh_layer.get_combat("loc2")
        assert r1 is not None
        assert r2 is not None
        assert r1.round_number == 2
        assert r1.turn_order == ["a", "b"]
        assert r2.round_number == 5
        assert r2.turn_order == ["d", "c"]
        assert r2.battle_map.width == 80
        assert r2.battle_map.get_position("c") == Position(10, 10)
