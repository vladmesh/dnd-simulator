"""Pure functions for D&D 5e opportunity attack eligibility and trigger detection.

No state, no I/O. Takes creatures and positions in, returns eligibility/triggers out.
"""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.rules.combat_sides import are_allies
from dnd_simulator.rules.conditions import is_incapacitated
from dnd_simulator.rules.movement import grid_distance
from dnd_simulator.rules.weapons import get_weapon_attack


def leaves_reach(reactor_pos: Position, reach: int, current: Position, next_pos: Position) -> bool:
    """The opportunity-attack trigger for one step: the mover was within *reach* and is now outside it.

    Entering a reach never triggers, nor does moving between two cells that are both within it.
    """
    return grid_distance(reactor_pos, current) <= reach < grid_distance(reactor_pos, next_pos)


def find_oa_triggers(
    path: list[Position],
    mover: Creature,
    combatants: list[Creature],
    battle_map: BattleMap,
    combat_state: CombatState | None = None,
) -> list[tuple[int, list[Creature]]]:
    """Find opportunity attack triggers along a movement path.

    For each step in the path, find combatants whose reach the mover is
    LEAVING (was in reach at step i, not in reach at step i+1).

    When combat_state is provided, allies (same combat side) are excluded
    from potential reactors — they don't provoke opportunity attacks.

    Returns (step_index, [reactors]) pairs. step_index is the position
    the mover is leaving FROM (i.e. the last position in reach).
    """
    if mover.is_disengaging:
        return []

    if len(path) < 2:
        return []

    # Filter to potential reactors (not the mover, alive, has reaction, not incapacitated, not allied)
    potential_reactors: list[tuple[Creature, Position, int]] = []
    for c in combatants:
        if c is mover:
            continue
        if not c.is_alive:
            continue
        if combat_state is not None and are_allies(combat_state, mover.id, c.id):
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
            if leaves_reach(creature_pos, reach, current_pos, next_pos):
                step_reactors.append(creature)

        if step_reactors:
            triggers.append((step_idx, step_reactors))

    return triggers
