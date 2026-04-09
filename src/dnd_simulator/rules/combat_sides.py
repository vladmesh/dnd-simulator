"""Pure functions for building combat sides from faction relations.

No state, no I/O. Takes creatures and a relation callback, returns side assignments.
"""

from __future__ import annotations

from collections.abc import Callable

from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.models import FactionRelation

RelationFn = Callable[[str, str], FactionRelation]


def build_combat_sides(
    creatures: list[Creature],
    get_relation: RelationFn,
) -> tuple[dict[int, set[str]], dict[str, int]]:
    """Build combat sides from creatures and faction relations.

    Greedy assignment algorithm:
    1. Group creatures by faction_id (same faction = same group).
       Creatures without faction_id each get their own side.
    2. Process faction groups in order. For each faction, find existing sides
       containing a FRIENDLY faction. If exactly one match, join it.
       If multiple matches, join the first. If none, create a new side.

    This avoids transitive merging: if A-FRIENDLY-C and B-FRIENDLY-C
    but A-HOSTILE-B, C joins one side without merging A and B.

    Returns (sides, entity_to_side):
      sides: side_index → set of entity IDs
      entity_to_side: entity_id → side_index
    """
    if not creatures:
        return {}, {}

    # Group creatures by faction_id. No faction → isolated.
    faction_groups: dict[str, list[str]] = {}
    isolated: list[str] = []
    for c in creatures:
        if not c.faction_id:
            isolated.append(c.id)
        else:
            faction_groups.setdefault(c.faction_id, []).append(c.id)

    sides: dict[int, set[str]] = {}
    entity_to_side: dict[str, int] = {}
    side_factions: dict[int, set[str]] = {}  # side → set of faction_ids on that side
    next_side = 0

    # Process each faction group: find a FRIENDLY existing side or create new.
    for faction_id, entity_ids in faction_groups.items():
        target_side: int | None = None
        for side_idx, factions_on_side in side_factions.items():
            for existing_faction in factions_on_side:
                if existing_faction == faction_id:
                    target_side = side_idx
                    break
                if get_relation(faction_id, existing_faction) == FactionRelation.FRIENDLY:
                    target_side = side_idx
                    break
            if target_side is not None:
                break

        if target_side is None:
            target_side = next_side
            sides[target_side] = set()
            side_factions[target_side] = set()
            next_side += 1

        sides[target_side].update(entity_ids)
        side_factions[target_side].add(faction_id)
        for eid in entity_ids:
            entity_to_side[eid] = target_side

    # Each factionless creature gets its own side.
    for eid in isolated:
        sides[next_side] = {eid}
        entity_to_side[eid] = next_side
        next_side += 1

    return sides, entity_to_side


def are_allies(combat: CombatState, a: str, b: str) -> bool:
    """Check if two entities are on the same combat side."""
    side_a = combat.entity_to_side.get(a)
    side_b = combat.entity_to_side.get(b)
    if side_a is None or side_b is None:
        return False
    return side_a == side_b
