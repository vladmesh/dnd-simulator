"""Focused unit tests for rules/reactions.py — find_oa_triggers.

Sprint 012, Phase 4, Task 3.
"""

from __future__ import annotations

from dnd_simulator.core.character import Ability, Attack, Creature, DamageComponent, DamageType
from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.reactions import find_oa_triggers

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _creature(
    id: str,
    *,
    hp: int = 20,
    reaction: int = 1,
    disengaging: bool = False,
    conditions: dict[Condition, int | None] | None = None,
    reach: int = 5,
) -> Creature:
    c = Creature(id=id, name=id.capitalize(), location_id="arena", max_hp=hp, current_hp=hp)
    c.turn_budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30, reaction=reaction)
    c.is_disengaging = disengaging
    if conditions:
        c.conditions = conditions
    # Set an attack with the given reach
    c.attacks = (
        Attack(
            name="melee",
            ability=Ability.STR,
            damage=(DamageComponent(dice="1d6", type=DamageType.SLASHING),),
            reach=reach,
        ),
    )
    return c


def _battle_map() -> BattleMap:
    return BattleMap(width=50, height=50)


# ---------------------------------------------------------------------------
# find_oa_triggers
# ---------------------------------------------------------------------------


class TestFindOaTriggers:
    def test_empty_path(self) -> None:
        """Empty path produces no triggers."""
        mover = _creature("goblin")
        bm = _battle_map()
        assert find_oa_triggers([], mover, [], bm) == []

    def test_single_position_path(self) -> None:
        """Path with only one position (no steps) produces no triggers."""
        mover = _creature("goblin")
        bm = _battle_map()
        assert find_oa_triggers([Position(10, 10)], mover, [], bm) == []

    def test_no_combatants(self) -> None:
        """Path with no combatants produces no triggers."""
        mover = _creature("goblin")
        bm = _battle_map()
        bm.set_position("goblin", Position(10, 10))
        path = [Position(10, 10), Position(10, 15), Position(10, 20)]
        assert find_oa_triggers(path, mover, [], bm) == []

    def test_leaving_reach_triggers(self) -> None:
        """Mover leaving a reactor's reach triggers OA at the correct step."""
        mover = _creature("goblin")
        guard = _creature("guard")
        bm = _battle_map()
        bm.set_position("goblin", Position(10, 10))
        bm.set_position("guard", Position(10, 15))  # adjacent at start
        # Path: (10,10) → (10,5). Guard at (10,15): dist goes 5 → 10. Leaves reach.
        path = [Position(10, 10), Position(10, 5)]
        triggers = find_oa_triggers(path, mover, [guard, mover], bm)
        assert len(triggers) == 1
        step_idx, reactors = triggers[0]
        assert step_idx == 0
        assert guard in reactors

    def test_multiple_reactors_same_step(self) -> None:
        """Two reactors lose reach at the same step."""
        mover = _creature("goblin")
        guard_a = _creature("guard_a")
        guard_b = _creature("guard_b")
        bm = _battle_map()
        bm.set_position("goblin", Position(10, 10))
        bm.set_position("guard_a", Position(5, 10))  # 5ft west, in reach
        bm.set_position("guard_b", Position(15, 10))  # 5ft east, in reach
        # Path: (10,10) → (10,20). Both go from 5ft to 10ft away. Leaves reach.
        path = [Position(10, 10), Position(10, 20)]
        triggers = find_oa_triggers(path, mover, [guard_a, guard_b, mover], bm)
        assert len(triggers) == 1
        _, reactors = triggers[0]
        assert guard_a in reactors
        assert guard_b in reactors

    def test_disengaging_mover_no_triggers(self) -> None:
        """Disengaging mover produces no triggers regardless of path."""
        mover = _creature("goblin", disengaging=True)
        guard = _creature("guard")
        bm = _battle_map()
        bm.set_position("goblin", Position(10, 10))
        bm.set_position("guard", Position(10, 15))
        path = [Position(10, 10), Position(10, 5)]
        assert find_oa_triggers(path, mover, [guard, mover], bm) == []

    def test_dead_combatant_excluded(self) -> None:
        """Dead combatant is not a potential reactor."""
        mover = _creature("goblin")
        dead_guard = _creature("guard", hp=0)
        dead_guard.current_hp = 0
        bm = _battle_map()
        bm.set_position("goblin", Position(10, 10))
        bm.set_position("guard", Position(10, 15))
        path = [Position(10, 10), Position(10, 5)]
        assert find_oa_triggers(path, mover, [dead_guard, mover], bm) == []

    def test_incapacitated_combatant_excluded(self) -> None:
        """Stunned combatant cannot react."""
        mover = _creature("goblin")
        stunned = _creature("guard", conditions={Condition.STUNNED: None})
        bm = _battle_map()
        bm.set_position("goblin", Position(10, 10))
        bm.set_position("guard", Position(10, 15))
        path = [Position(10, 10), Position(10, 5)]
        assert find_oa_triggers(path, mover, [stunned, mover], bm) == []

    def test_no_reaction_budget_excluded(self) -> None:
        """Combatant with 0 reactions is excluded."""
        mover = _creature("goblin")
        spent = _creature("guard", reaction=0)
        bm = _battle_map()
        bm.set_position("goblin", Position(10, 10))
        bm.set_position("guard", Position(10, 15))
        path = [Position(10, 10), Position(10, 5)]
        assert find_oa_triggers(path, mover, [spent, mover], bm) == []
