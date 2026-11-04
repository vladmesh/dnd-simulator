"""Coverage for Sneak Attack ally detection with missing targets and ineligible allies."""

import pytest
from test_sneak_attack_faction import _fighter, _goblin, _rogue

from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.rules.sneak_attack import find_adjacent_ally


@pytest.mark.parametrize(
    ("ally_hp", "ally_position", "expected_adjacent"),
    [(30, Position(35, 35), True), (0, Position(35, 35), False), (30, Position(35, 40), False)],
    ids=["living-adjacent-ally", "dead-ally", "distant-ally"],
)
def test_find_adjacent_ally_requires_living_adjacent_ally_and_positioned_target(
    ally_hp: int, ally_position: Position, expected_adjacent: bool
) -> None:
    attacker = _rogue()
    target = _goblin(entity_id="target")
    ally = _fighter()
    ally.current_hp = ally_hp
    entities = {creature.id: creature for creature in (attacker, target, ally)}
    battle_map = BattleMap(width=60, height=60)
    battle_map.set_position(attacker.id, Position(30, 30))
    battle_map.set_position(target.id, Position(35, 30))
    battle_map.set_position(ally.id, ally_position)

    def is_ally(entity_id: str) -> bool:
        return entities[entity_id].faction_id == attacker.faction_id

    assert (
        find_adjacent_ally(
            attacker_id=attacker.id,
            target_id=target.id,
            battle_map=battle_map,
            entities=entities,
            is_ally=is_ally,
        )
        is expected_adjacent
    )

    battle_map.remove(target.id)

    assert (
        find_adjacent_ally(
            attacker_id=attacker.id,
            target_id=target.id,
            battle_map=battle_map,
            entities=entities,
            is_ally=is_ally,
        )
        is False
    )
