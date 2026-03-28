"""Tests for reachable cells in combat awareness pipeline."""

from __future__ import annotations

from dataclasses import replace

from dnd_simulator.core.awareness import CombatAwareness
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.combat import BattleMap, Position, Wall
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.rules.movement import compute_reachable
from dnd_simulator.service.session import _awareness_to_dict

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)


def _scores(**overrides: int) -> AbilityScores:
    scores = dict(AbilityScores().scores)
    for name, val in overrides.items():
        scores[Ability[name.upper()]] = val
    return AbilityScores(scores=scores)


class TestCombatAwarenessReachable:
    """CombatAwareness includes reachable cells computed by backend."""

    def test_reachable_contains_expected_positions(self) -> None:
        """Build combat awareness, inject reachable via replace — verify positions."""
        player = Character(
            id="p1",
            name="Hero",
            location_id="r1",
            max_hp=20,
            current_hp=20,
            attacks=(_SWORD,),
        )
        enemy = Character(id="e1", name="Goblin", location_id="r1")
        layer = EntitiesLayer([player, enemy])
        # Set up combat with a battle map with a full vertical wall
        layer._combat.start_combat("r1")
        combat = layer._combat.get_combat("r1")
        assert combat is not None
        bm = BattleMap(
            width=20,
            height=20,
            walls=[Wall(x1=10, y1=0, x2=10, y2=25)],  # full vertical wall, no way around
        )
        bm.set_position("p1", Position(5, 5))
        bm.set_position("e1", Position(15, 5))
        combat.battle_map = bm

        awareness = layer.build_combat_awareness(player)

        # Simulate what Round does: compute reachable and inject via replace
        my_pos = Position(5, 5)
        reachable_map = compute_reachable(my_pos, budget=30, battle_map=bm, mover_id="p1")
        reachable = frozenset((p.x, p.y) for p in reachable_map if p != my_pos)
        awareness = replace(awareness, reachable=reachable)

        # Position (0, 5) should be reachable (straight west, no wall)
        assert (0, 5) in awareness.reachable
        # Positions east of wall should NOT be reachable — full vertical wall blocks
        assert (10, 5) not in awareness.reachable
        assert (15, 5) not in awareness.reachable
        assert (20, 5) not in awareness.reachable

    def test_reachable_respects_wall_blocking(self) -> None:
        """Cells behind walls are excluded from reachable set."""
        # Full vertical wall — nothing east should be reachable
        bm = BattleMap(
            width=20,
            height=20,
            walls=[Wall(x1=10, y1=0, x2=10, y2=25)],
        )
        bm.set_position("p1", Position(5, 5))

        my_pos = Position(5, 5)
        reachable_map = compute_reachable(my_pos, budget=30, battle_map=bm, mover_id="p1")
        reachable = frozenset((p.x, p.y) for p in reachable_map if p != my_pos)

        # Nothing east of the wall should be reachable
        for pos_tuple in reachable:
            assert pos_tuple[0] < 10, f"Position {pos_tuple} should not be reachable (behind wall)"

    def test_reachable_empty_when_not_turn_taker(self) -> None:
        """Default CombatAwareness has empty reachable — not the creature's turn."""
        awareness = CombatAwareness(
            self_hp=20,
            self_max_hp=20,
            self_ac=15,
            self_speed=30,
            self_weapon="longsword",
            self_weapon_damage="1d8",
        )
        assert awareness.reachable == frozenset()

    def test_reachable_empty_with_zero_budget(self) -> None:
        """Zero movement budget → empty reachable."""
        bm = BattleMap(width=20, height=20)
        bm.set_position("p1", Position(5, 5))

        my_pos = Position(5, 5)
        reachable_map = compute_reachable(my_pos, budget=0, battle_map=bm, mover_id="p1")
        reachable = frozenset((p.x, p.y) for p in reachable_map if p != my_pos)
        assert reachable == frozenset()


class TestReachableSerialization:
    """Serialization of reachable field for the frontend."""

    def test_awareness_to_dict_includes_reachable(self) -> None:
        """_awareness_to_dict serializes reachable as list of [x, y] pairs."""
        awareness = CombatAwareness(
            self_hp=20,
            self_max_hp=20,
            self_ac=15,
            self_speed=30,
            self_weapon="longsword",
            self_weapon_damage="1d8",
            reachable=frozenset({(5, 10), (10, 5), (0, 0)}),
        )
        d = _awareness_to_dict(awareness)
        assert "reachable" in d
        # Should be a list of [x, y] pairs
        reachable_list = d["reachable"]
        assert isinstance(reachable_list, list)
        # Convert to set of tuples for order-independent comparison
        as_tuples = {tuple(pair) for pair in reachable_list}
        assert as_tuples == {(5, 10), (10, 5), (0, 0)}

    def test_empty_reachable_serializes_to_empty_list(self) -> None:
        """Empty reachable → empty list in dict."""
        awareness = CombatAwareness(
            self_hp=20,
            self_max_hp=20,
            self_ac=15,
            self_speed=30,
            self_weapon="longsword",
            self_weapon_damage="1d8",
        )
        d = _awareness_to_dict(awareness)
        assert d["reachable"] == []
