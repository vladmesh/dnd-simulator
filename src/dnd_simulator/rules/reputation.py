"""Pure functions for reputation-based relation resolution.

No state, no I/O. The single source of truth for how two creatures relate.
"""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import FactionRelation, QueryFn
from dnd_simulator.core.queries import query_faction_relation
from dnd_simulator.rules.combat_sides import FactionRelationFn


def make_relation_fn(query_fn: QueryFn) -> FactionRelationFn:
    """Adapt a raw ``query_fn`` into a ``(faction_a, faction_b) -> FactionRelation`` callback.

    Single source for the closure that combat, awareness, and activation all hand-rolled
    identically. Callers guard ``query_fn is not None`` before building the callback.
    """

    def get_faction_relation(a: str, b: str) -> FactionRelation:
        return query_faction_relation(query_fn, a, b)

    return get_faction_relation


FRIENDLY_THRESHOLD = 75
HOSTILE_THRESHOLD = 25
BASE_KILL_REPUTATION_DELTA = 20
DEFAULT_OWN_FACTION_REP = 100

# Default personal rep when materializing from faction-to-faction relation.
_RELATION_TO_DEFAULT_REP: dict[FactionRelation, int] = {
    FactionRelation.HOSTILE: 0,
    FactionRelation.NEUTRAL: 50,
    FactionRelation.FRIENDLY: 100,
}


def default_rep_for_faction(
    killer: Creature,
    victim_faction_id: str,
    get_faction_relation: FactionRelationFn,
) -> int:
    """Compute the starting personal reputation when none is stored.

    Uses faction-to-faction relation to determine the initial value:
    HOSTILE → 0, NEUTRAL → 50, FRIENDLY → 100.
    Same faction defaults to 100 (own-faction standing).
    """
    if not killer.faction_id or not victim_faction_id:
        return 50
    if killer.faction_id == victim_faction_id:
        return DEFAULT_OWN_FACTION_REP
    relation = get_faction_relation(killer.faction_id, victim_faction_id)
    return _RELATION_TO_DEFAULT_REP.get(relation, 50)


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


def apply_reputation_drop(
    killer: Creature,
    victim: Creature,
    base_delta: int,
    get_faction_relation: FactionRelationFn | None = None,
) -> int:
    """Apply reputation drop to killer for killing victim. Returns actual delta applied.

    Mutates killer.reputation. Clamps at 0.
    When get_faction_relation is provided, the initial personal reputation is
    derived from the faction-to-faction relation (HOSTILE→0, NEUTRAL→50, FRIENDLY→100)
    instead of always defaulting to 100.
    """
    delta = compute_kill_reputation_delta(base_delta, victim)
    if delta == 0:
        return 0
    faction_id = victim.faction_id
    if faction_id in killer.reputation:
        current = killer.reputation[faction_id]
    elif get_faction_relation is not None:
        current = default_rep_for_faction(killer, faction_id, get_faction_relation)
    else:
        current = DEFAULT_OWN_FACTION_REP
    actual_delta = min(delta, current)
    killer.reputation[faction_id] = current - actual_delta
    return actual_delta
