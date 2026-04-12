"""Architectural tests for RuleBrain's location in rules/.

Phase 3 Task 2 of sprint 016 moved RuleBrain from core/brain.py to rules/rule_brain.py.
This file enforces that boundary: core/ must not depend on rules/.
"""

from __future__ import annotations

import re
from pathlib import Path

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity
from dnd_simulator.core.character import Ability, Attack, DamageComponent, DamageType
from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.rules.movement import direction_label, grid_distance
from dnd_simulator.rules.rule_brain import RuleBrain

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
    reach=5,
)


def _build_combat_awareness(npc: Npc, enemies: list[Npc], battle_map: BattleMap) -> CombatAwareness:
    my_pos = battle_map.get_position(npc.id)
    assert my_pos is not None
    nearby: list[CombatEntity] = []
    for e in enemies:
        if e.id == npc.id:
            continue
        other_pos = battle_map.get_position(e.id)
        assert other_pos is not None
        dist = grid_distance(my_pos, other_pos)
        dx = other_pos.x - my_pos.x
        dy = other_pos.y - my_pos.y
        nearby.append(
            CombatEntity(
                id=e.id,
                description=e.name,
                distance_ft=dist,
                direction=direction_label(dx, dy),
                x=other_pos.x,
                y=other_pos.y,
                is_hostile=True,
                is_wounded=False,
            )
        )
    return CombatAwareness(
        self_hp=npc.current_hp,
        self_max_hp=npc.max_hp,
        self_ac=npc.ac,
        self_speed=npc.speed,
        self_weapon="longsword",
        self_weapon_damage="1d8",
        self_x=my_pos.x,
        self_y=my_pos.y,
        nearby=nearby,
        turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=npc.speed, reaction=True),
        available_actions=[ActionType.ATTACK, ActionType.MOVE, ActionType.DISENGAGE],
    )


def test_core_brain_has_no_rules_imports() -> None:
    """core/brain.py must not import from rules/ (neither top-level nor lazy)."""
    brain_path = Path(__file__).resolve().parents[2] / "src" / "dnd_simulator" / "core" / "brain.py"
    text = brain_path.read_text()
    # Catch both top-level and in-function imports.
    assert not re.search(r"from\s+dnd_simulator\.rules", text), (
        "core/brain.py must not import from dnd_simulator.rules — RuleBrain lives in rules/rule_brain.py"
    )
    assert not re.search(r"import\s+dnd_simulator\.rules", text), (
        "core/brain.py must not import dnd_simulator.rules modules"
    )


def test_core_brain_does_not_define_rulebrain() -> None:
    """RuleBrain moved out of core/brain.py — it should no longer be defined there."""
    import dnd_simulator.core.brain as core_brain

    assert not hasattr(core_brain, "RuleBrain"), (
        "RuleBrain should live in dnd_simulator.rules.rule_brain, not core.brain"
    )


def test_rule_brain_importable_from_rules() -> None:
    """RuleBrain is importable from the new rules.rule_brain module."""
    import dnd_simulator.rules.rule_brain as rule_brain_module

    assert rule_brain_module.RuleBrain is RuleBrain


def test_rule_brain_attacks_enemy_in_reach() -> None:
    """Smoke integration test: RuleBrain picks attack when enemy is within reach."""
    npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
    enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
    bm = BattleMap(width=30, height=30)
    bm.set_position("n1", Position(10, 10))
    bm.set_position("e1", Position(10, 11))  # 5 ft adjacent
    awareness = _build_combat_awareness(npc, [npc, enemy], bm)

    action = RuleBrain().choose_action(npc, awareness, [])

    assert action.name == ActionType.ATTACK
    assert action.params["target_id"] == "e1"


def test_rule_brain_retreat_when_disengaging_low_hp() -> None:
    """RuleBrain moves away from nearest enemy when disengaging (exercises _move_away_from)."""
    npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=2)
    npc.is_disengaging = True
    enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
    bm = BattleMap(width=30, height=30)
    bm.set_position("n1", Position(10, 10))
    bm.set_position("e1", Position(10, 11))
    awareness = _build_combat_awareness(npc, [npc, enemy], bm)

    action = RuleBrain().choose_action(npc, awareness, [])

    assert action.name == ActionType.MOVE
    # Moving away from enemy to the north means direction should take us further from (10, 11)
    assert "direction" in action.params
