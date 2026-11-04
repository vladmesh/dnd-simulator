"""Coverage for opportunity attack reactors missing a battle-map position."""

from dnd_simulator.core.character import Ability, Attack, Creature, DamageComponent, DamageType
from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.reactions import find_oa_triggers


def _creature(creature_id: str) -> Creature:
    return Creature(
        id=creature_id,
        name=creature_id.capitalize(),
        location_id="arena",
        max_hp=20,
        current_hp=20,
        turn_budget=TurnBudget(actions=1, bonus_actions=0, movement_remaining=30, reaction=1),
        attacks=(
            Attack(
                name="melee",
                ability=Ability.STR,
                damage=(DamageComponent(dice="1d6", type=DamageType.SLASHING),),
                reach=5,
            ),
        ),
    )


def test_unplaced_reactor_is_skipped_until_added_to_battle_map() -> None:
    mover = _creature("mover")
    unplaced_guard = _creature("unplaced_guard")
    placed_guard = _creature("placed_guard")
    battle_map = BattleMap(width=50, height=50)
    battle_map.set_position(mover.id, Position(10, 10))
    battle_map.set_position(placed_guard.id, Position(5, 10))
    path = [Position(10, 10), Position(10, 5), Position(10, 0)]
    combatants = [unplaced_guard, placed_guard, mover]

    assert find_oa_triggers(path, mover, combatants, battle_map) == [(1, [placed_guard])]

    battle_map.set_position(unplaced_guard.id, Position(15, 10))

    assert find_oa_triggers(path, mover, combatants, battle_map) == [(1, [unplaced_guard, placed_guard])]
