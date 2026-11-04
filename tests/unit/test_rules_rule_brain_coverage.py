"""Coverage for RuleBrain decisions when fleeing or retreating is unavailable."""

import pytest

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity
from dnd_simulator.core.character import Creature
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.rule_brain import RuleBrain


def _creature(*, hp: int = 20, disengaging: bool = False) -> Creature:
    return Creature(
        id="goblin",
        name="Goblin",
        location_id="arena",
        current_hp=hp,
        max_hp=20,
        speed=30,
        is_disengaging=disengaging,
    )


def _awareness(
    creature: Creature,
    *,
    hostile: bool = True,
    distance: int = 5,
    movement: int = 30,
    map_size: int = 30,
) -> CombatAwareness:
    return CombatAwareness(
        self_hp=creature.current_hp,
        self_max_hp=creature.max_hp,
        self_ac=creature.ac,
        self_speed=creature.speed,
        self_weapon="fists",
        self_weapon_damage="1",
        nearby=[
            CombatEntity(
                id="other",
                description="Bandit",
                is_hostile=hostile,
                distance_ft=distance,
                x=distance,
                y=0,
            ),
        ],
        battle_map_width=map_size,
        battle_map_height=map_size,
        occupied_cells=frozenset({(distance, 0)}),
        turn_budget=TurnBudget(actions=1, bonus_actions=0, movement_remaining=movement),
    )


@pytest.mark.parametrize("movement", [0, 4])
def test_pinned_wounded_creature_dashes_when_it_cannot_step_back(movement: int) -> None:
    creature = _creature(hp=1)
    awareness = _awareness(creature, distance=10, movement=movement)

    action = RuleBrain().choose_action(creature, awareness, [])

    assert action == Action(name=ActionType.DASH)


@pytest.mark.parametrize(
    ("hostile", "map_size", "expected"),
    [
        pytest.param(True, 0, Action(name=ActionType.ATTACK, params={"target_id": "other"}), id="unknown-map"),
        pytest.param(False, 30, END_TURN, id="no-threats"),
    ],
)
def test_disengaging_creature_falls_back_when_retreat_cannot_be_planned(
    hostile: bool, map_size: int, expected: Action
) -> None:
    creature = _creature(disengaging=True)
    awareness = _awareness(creature, hostile=hostile, map_size=map_size)

    action = RuleBrain().choose_action(creature, awareness, [])

    assert action == expected


def test_disengaging_creature_attacks_when_no_cell_increases_clearance() -> None:
    creature = _creature(disengaging=True)
    awareness = _awareness(creature, map_size=5)

    action = RuleBrain().choose_action(creature, awareness, [])

    assert action == Action(name=ActionType.ATTACK, params={"target_id": "other"})
