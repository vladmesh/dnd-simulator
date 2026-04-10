"""Pure functions for reputation-based relation resolution.

No state, no I/O. The single source of truth for how two creatures relate.
"""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import FactionRelation
from dnd_simulator.rules.combat_sides import RelationFn

FRIENDLY_THRESHOLD = 75
HOSTILE_THRESHOLD = 25


def reputation_to_relation(rep: int) -> FactionRelation:
    """Convert a numeric reputation score to a faction relation via thresholds."""
    if rep >= FRIENDLY_THRESHOLD:
        return FactionRelation.FRIENDLY
    if rep < HOSTILE_THRESHOLD:
        return FactionRelation.HOSTILE
    return FactionRelation.NEUTRAL


def effective_relation(
    a: Creature,
    b: Creature,
    get_faction_relation: RelationFn,
) -> FactionRelation:
    """Determine how creature A relates to creature B.

    Priority:
    1. If either creature has no faction — NEUTRAL.
    2. If A has a personal reputation entry for B's faction — apply thresholds.
    3. Otherwise — fall back to faction-to-faction relation.
    """
    if not a.faction_id or not b.faction_id:
        return FactionRelation.NEUTRAL

    personal_rep = a.reputation.get(b.faction_id)
    if personal_rep is not None:
        return reputation_to_relation(personal_rep)

    return get_faction_relation(a.faction_id, b.faction_id)
