"""Pure functions for building combat sides from creature relations.

No state, no I/O. Takes creatures and a relation callback, returns side assignments.
"""

from __future__ import annotations

from collections.abc import Callable

from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.models import FactionRelation

FactionRelationFn = Callable[[str, str], FactionRelation]
CreatureRelationFn = Callable[[Creature, Creature], FactionRelation]


def build_combat_sides(
    creatures: list[Creature],
    get_relation: CreatureRelationFn,
    forced_opponents: set[tuple[str, str]] | None = None,
) -> tuple[dict[int, set[str]], dict[str, int]]:
    """Build combat sides from creatures and their pairwise relations.

    Creature-level greedy assignment:
    1. Process creatures one by one.
    2. Factionless creatures each get their own side.
    3. For each creature, check existing sides. To join a side, the creature
       must be mutually FRIENDLY with ALL members (both directions checked).
       Any HOSTILE in either direction → skip that side.
       Also skip sides containing a forced opponent.
    4. If no side matches, create a new one.

    ``forced_opponents`` is a set of (id_a, id_b) pairs that must end up on
    different sides regardless of faction relations. Used when an attack
    triggers combat — attacker and target are always opponents.

    Returns (sides, entity_to_side):
      sides: side_index → set of entity IDs
      entity_to_side: entity_id → side_index
    """
    if not creatures:
        return {}, {}

    # Build a fast lookup: entity_id → set of entity_ids it must not share a side with
    opponent_of: dict[str, set[str]] = {}
    if forced_opponents:
        for a, b in forced_opponents:
            opponent_of.setdefault(a, set()).add(b)
            opponent_of.setdefault(b, set()).add(a)

    creature_by_id: dict[str, Creature] = {c.id: c for c in creatures}
    sides: dict[int, set[str]] = {}
    entity_to_side: dict[str, int] = {}
    for creature in creatures:
        join_side(creature, sides, entity_to_side, creature_by_id, get_relation, opponent_of.get(creature.id, set()))
    return sides, entity_to_side


def join_side(
    creature: Creature,
    sides: dict[int, set[str]],
    entity_to_side: dict[str, int],
    creature_by_id: dict[str, Creature],
    get_relation: CreatureRelationFn,
    opponents: set[str] | frozenset[str] = frozenset(),
) -> int:
    """Put one creature on the first side it is mutually FRIENDLY with, else on a new side.

    Mutates ``sides`` / ``entity_to_side`` in place and returns the side index. A factionless
    creature always gets a side of its own; a side holding one of ``opponents`` is skipped.
    ``creature_by_id`` must resolve every current side member. Used for each creature when
    a combat starts and for a creature joining a running combat.
    """
    target_side: int | None = None
    if creature.faction_id:
        for side_idx, members in sides.items():
            if opponents & members:
                continue
            if all(
                get_relation(creature, creature_by_id[member_id]) == FactionRelation.FRIENDLY
                and get_relation(creature_by_id[member_id], creature) == FactionRelation.FRIENDLY
                for member_id in members
            ):
                target_side = side_idx
                break
    if target_side is None:
        target_side = max(sides, default=-1) + 1
        sides[target_side] = set()
    sides[target_side].add(creature.id)
    entity_to_side[creature.id] = target_side
    return target_side


def are_allies(combat: CombatState, a: str, b: str) -> bool:
    """Check if two entities are on the same combat side."""
    side_a = combat.entity_to_side.get(a)
    side_b = combat.entity_to_side.get(b)
    if side_a is None or side_b is None:
        return False
    return side_a == side_b
