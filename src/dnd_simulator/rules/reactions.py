"""Pure functions for D&D 5e opportunity attack eligibility and trigger detection.

No state, no I/O. Takes creatures and positions in, returns eligibility/triggers out.
"""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.rules.conditions import is_incapacitated
from dnd_simulator.rules.movement import grid_distance
from dnd_simulator.rules.weapons import get_weapon_attack


def can_opportunity_attack(reactor: Creature, mover: Creature, battle_map: BattleMap) -> bool:
    """Check if reactor can make an opportunity attack against mover.

    Requires: reactor alive, not incapacitated, has reaction budget,
    mover in weapon reach, mover not disengaging, reactor is not the mover.
    """
    if reactor is mover:
        return False
    if not reactor.is_alive:
        return False
    if is_incapacitated(reactor.conditions):
        return False
    if reactor.turn_budget is None or reactor.turn_budget.reaction <= 0:
        return False
    if mover.is_disengaging:
        return False

    reactor_pos = battle_map.get_position(reactor.id)
    mover_pos = battle_map.get_position(mover.id)
    if reactor_pos is None or mover_pos is None:
        return False

    reach = get_weapon_attack(reactor).reach
    distance = grid_distance(reactor_pos, mover_pos)
    return distance <= reach


def find_oa_triggers(
    path: list[Position],
    mover: Creature,
    combatants: list[Creature],
    battle_map: BattleMap,
) -> list[tuple[int, list[Creature]]]:
    """Find opportunity attack triggers along a movement path.

    For each step in the path, find combatants whose reach the mover is
    LEAVING (was in reach at step i, not in reach at step i+1).

    Returns (step_index, [reactors]) pairs. step_index is the position
    the mover is leaving FROM (i.e. the last position in reach).
    """
    if mover.is_disengaging:
        return []

    if len(path) < 2:
        return []

    # Filter to potential reactors (not the mover, alive, has reaction, not incapacitated)
    potential_reactors: list[tuple[Creature, Position, int]] = []
    for c in combatants:
        if c is mover:
            continue
        if not c.is_alive:
            continue
        if is_incapacitated(c.conditions):
            continue
        if c.turn_budget is None or c.turn_budget.reaction <= 0:
            continue
        pos = battle_map.get_position(c.id)
        if pos is None:
            continue
        reach = get_weapon_attack(c).reach
        potential_reactors.append((c, pos, reach))

    triggers: list[tuple[int, list[Creature]]] = []

    for step_idx in range(len(path) - 1):
        current_pos = path[step_idx]
        next_pos = path[step_idx + 1]

        step_reactors: list[Creature] = []
        for creature, creature_pos, reach in potential_reactors:
            dist_current = grid_distance(creature_pos, current_pos)
            dist_next = grid_distance(creature_pos, next_pos)
            # Trigger: was in reach, now leaving reach
            if dist_current <= reach and dist_next > reach:
                step_reactors.append(creature)

        if step_reactors:
            triggers.append((step_idx, step_reactors))

    return triggers
