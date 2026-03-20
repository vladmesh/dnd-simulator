"""Tests for RuleBrain utility-scoring combat AI."""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.brain import RuleBrain
from dnd_simulator.core.character import (
    Ability,
    Attack,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.models import ActionResult, GameDateTime
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
    reach=5,
)


def _make_world(entities: list[object], battle_map: BattleMap | None = None) -> MagicMock:
    """Build a mock World backed by a real EntitiesLayer for combat awareness."""
    layer = EntitiesLayer(entities=entities)  # type: ignore[arg-type]
    world = MagicMock()
    world.time = GameDateTime(year=1, month=1, day=1, hour=12)
    world.layers = [layer]
    world.handle_event.return_value = ActionResult()

    # Start combat if multiple creatures in same region
    combat_region = entities[0].region_id if entities else "arena"  # type: ignore[union-attr]
    for e in entities:
        if hasattr(e, "in_combat"):
            e.in_combat = True  # type: ignore[union-attr]
    combat = CombatState(
        region_id=combat_region,
        turn_order=[e.id for e in entities],  # type: ignore[union-attr]
    )
    if battle_map is not None:
        combat.battle_map = battle_map
    layer._combats[combat_region] = combat

    def fake_query(layer_name: str, query: object) -> MagicMock:
        if layer_name == "entities":
            return layer.query(query)  # type: ignore[arg-type]
        answer = MagicMock()
        answer.value = None
        return answer

    world.query_layer.side_effect = fake_query
    return world


class TestRuleBrainPeaceful:
    def test_peaceful_returns_idle(self) -> None:
        npc = Npc(id="n1", name="Guard", region_id="r1", attacks=(_SWORD,))
        npc.in_combat = False
        brain = RuleBrain()
        world = MagicMock()
        action = brain.choose_action(npc, world)
        assert action.name == "idle"


class TestRuleBrainCombat:
    def test_attack_when_in_reach(self) -> None:
        npc = Npc(id="n1", name="Guard", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        enemy = Npc(id="e1", name="Bandit", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))  # 5 ft away — in reach
        world = _make_world([npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, world)
        assert action.name == "attack"
        assert action.params["target_id"] == "e1"

    def test_move_toward_when_close_but_not_in_reach(self) -> None:
        npc = Npc(id="n1", name="Guard", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20, speed=30)
        enemy = Npc(id="e1", name="Bandit", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 30))  # 20 ft away — within speed+reach=35
        world = _make_world([npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, world)
        assert action.name == "move"
        assert action.params["toward"] == "e1"

    def test_dash_when_far(self) -> None:
        npc = Npc(id="n1", name="Guard", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20, speed=30)
        enemy = Npc(id="e1", name="Bandit", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=120, height=120)
        bm.set_position("n1", Position(0, 0))
        bm.set_position("e1", Position(60, 60))  # ~60 ft away — beyond speed+reach
        world = _make_world([npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, world)
        assert action.name == "dash"
        assert action.params["toward"] == "e1"

    def test_flee_when_critically_wounded(self) -> None:
        npc = Npc(id="n1", name="Guard", region_id="arena", attacks=(_SWORD,), max_hp=100, current_hp=10)
        enemy = Npc(id="e1", name="Bandit", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))
        world = _make_world([npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, world)
        assert action.name == "flee"

    def test_dodge_when_badly_hurt_and_in_reach(self) -> None:
        npc = Npc(id="n1", name="Guard", region_id="arena", attacks=(_SWORD,), max_hp=100, current_hp=20)
        enemy = Npc(id="e1", name="Bandit", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))  # 5 ft — in reach
        world = _make_world([npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, world)
        assert action.name == "dodge"

    def test_idle_when_no_enemies(self) -> None:
        npc = Npc(id="n1", name="Guard", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        world = _make_world([npc], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, world)
        assert action.name == "idle"

    def test_attacks_nearest_of_multiple_enemies(self) -> None:
        npc = Npc(id="n1", name="Guard", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        far = Npc(id="far", name="Far", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        close = Npc(id="close", name="Close", region_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("far", Position(10, 40))
        bm.set_position("close", Position(10, 15))
        world = _make_world([npc, far, close], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, world)
        assert action.name == "attack"
        assert action.params["target_id"] == "close"
