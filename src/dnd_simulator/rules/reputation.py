"""Pure functions for reputation-based relation resolution.

No state, no I/O. The single source of truth for how two creatures relate.
"""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import FactionRelation
from dnd_simulator.rules.combat_sides import FactionRelationFn

FRIENDLY_THRESHOLD = 75
HOSTILE_THRESHOLD = 25
BASE_KILL_REPUTATION_DELTA = 20
DEFAULT_OWN_FACTION_REP = 100


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
    get_faction_relation: FactionRelationFn,
) -> FactionRelation:
    """Determine how creature A relates to creature B.

    Priority:
    1. If either creature has no faction — NEUTRAL.
    2. If A has a personal reputation entry for B's faction — apply thresholds.
    3. Same faction with no personal override — FRIENDLY.
    4. Otherwise — fall back to faction-to-faction relation.
    """
    if not a.faction_id or not b.faction_id:
        return FactionRelation.NEUTRAL

    personal_rep = a.reputation.get(b.faction_id)
    if personal_rep is not None:
        return reputation_to_relation(personal_rep)

    if a.faction_id == b.faction_id:
        return FactionRelation.FRIENDLY

    return get_faction_relation(a.faction_id, b.faction_id)


def compute_kill_reputation_delta(base_delta: int, victim: Creature) -> int:
    """Compute reputation drop for killing a creature.

    Scaled by victim's standing with own faction:
    delta = base_delta * (victim_rep_with_own_faction / 100).
    Killing an outcast costs nothing; killing a respected member costs full delta.
    """
    if not victim.faction_id:
        return 0
    victim_own_rep = victim.reputation.get(victim.faction_id, DEFAULT_OWN_FACTION_REP)
    return base_delta * victim_own_rep // 100


def apply_reputation_drop(killer: Creature, victim: Creature, base_delta: int) -> int:
    """Apply reputation drop to killer for killing victim. Returns actual delta applied.

    Mutates killer.reputation. Clamps at 0.
    """
    delta = compute_kill_reputation_delta(base_delta, victim)
    if delta == 0:
        return 0
    faction_id = victim.faction_id
    current = killer.reputation.get(faction_id, DEFAULT_OWN_FACTION_REP)
    actual_delta = min(delta, current)
    killer.reputation[faction_id] = current - actual_delta
    return actual_delta
