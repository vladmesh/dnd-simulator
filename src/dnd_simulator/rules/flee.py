"""Flee rules — who may leave a fight, and where to.

Pure functions, no state, no I/O. Flee is a real exit from the scene: the fleer
leaves combat and travels one location-graph edge. It never rolls — it is legal
only when no living enemy stands within ``FLEE_SAFE_DISTANCE_FT`` of the fleer
on the battle map, and when the location has somewhere to go.

``flee_blocker`` is the single eligibility rule. Validation (every brain, every
dispatch), the RuleBrain and the player's UI payload all read it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from enum import StrEnum
from typing import TYPE_CHECKING

from dnd_simulator.core.awareness import FleeDestination, FleeStatus
from dnd_simulator.i18n import _

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature, Entity
    from dnd_simulator.core.combat import CombatState
    from dnd_simulator.core.location import LocationGraph

FLEE_SAFE_DISTANCE_FT = 15  # three cells: an enemy this close (or closer) blocks a flee


class FleeBlock(StrEnum):
    """Why a flee is not allowed right now (machine-readable key for the UI)."""

    ENEMIES_TOO_CLOSE = "enemies_too_close"
    NO_EXIT = "no_exit"


def flee_block_message(block: FleeBlock) -> str:
    """Localized, player-facing explanation of a flee block."""
    if block is FleeBlock.ENEMIES_TOO_CLOSE:
        return _("Enemies are too close to flee")
    return _("There is nowhere to flee")


def enemy_blocks_flee(distance_ft: int) -> bool:
    """An enemy at this distance keeps the fleer pinned to the fight."""
    return distance_ft <= FLEE_SAFE_DISTANCE_FT


def is_enemy(combat: CombatState, actor: Creature, other: Creature) -> bool:
    """Whether *other* fights against *actor* in this combat.

    Combat sides decide when both are on a side. A combat started without sides
    (e.g. an encounter auto-combat) falls back to factions, the same way
    ``CombatManager._has_opposing_factions`` does: an unknown or different
    faction is an enemy.
    """
    side_a = combat.entity_to_side.get(actor.id)
    side_b = combat.entity_to_side.get(other.id)
    if side_a is not None and side_b is not None:
        return side_a != side_b
    if not actor.faction_id or not other.faction_id:
        return True
    return actor.faction_id != other.faction_id


def flee_blocker(
    actor: Creature,
    combat: CombatState | None,
    get_entity: Callable[[str], Entity | None] | None,
    exits: Iterable[str] | None = None,
) -> FleeBlock | None:
    """Return why *actor* may not flee now, or None if the flee is legal.

    ``exits`` is the list of neighbouring location ids; pass None when the
    location graph is unknown to the caller (the handler still checks it).
    """
    from dnd_simulator.core.character import Creature as CreatureType
    from dnd_simulator.rules.movement import grid_distance

    if exits is not None and not list(exits):
        return FleeBlock.NO_EXIT
    if combat is None or get_entity is None:
        return None
    bm = combat.battle_map
    own = bm.get_position(actor.id)
    if own is None:
        return None
    for other_id in combat.turn_order:
        if other_id == actor.id:
            continue
        other = get_entity(other_id)
        if not isinstance(other, CreatureType) or not other.is_alive:
            continue
        if not is_enemy(combat, actor, other):
            continue
        pos = bm.get_position(other_id)
        if pos is not None and enemy_blocks_flee(grid_distance(own, pos)):
            return FleeBlock.ENEMIES_TOO_CLOSE
    return None


def flee_destinations(graph: LocationGraph, location_id: str) -> tuple[FleeDestination, ...]:
    """Every neighbour one edge away, with display name and edge travel time."""
    if not graph.has(location_id):
        return ()
    result: list[FleeDestination] = []
    for edge in graph.neighbors(location_id):
        name = graph.get(edge.target_id).name if graph.has(edge.target_id) else edge.target_id
        result.append(FleeDestination(edge.target_id, name, graph.travel_seconds(location_id, edge.target_id)))
    return tuple(result)


def flee_status(
    actor: Creature,
    combat: CombatState | None,
    get_entity: Callable[[str], Entity | None] | None,
    graph: LocationGraph | None,
) -> FleeStatus:
    """Build the UI/brain view of flee availability from ``flee_blocker``."""
    destinations = flee_destinations(graph, actor.location_id) if graph is not None else ()
    block = flee_blocker(actor, combat, get_entity, [d.id for d in destinations] if graph is not None else None)
    if block is None:
        return FleeStatus(allowed=True, destinations=destinations)
    return FleeStatus(
        allowed=False, reason_key=block.value, reason=flee_block_message(block), destinations=destinations
    )


def choose_flee_destination(
    destinations: Iterable[FleeDestination],
    home_first_hop: str | None = None,
    enemy_presence: Mapping[str, int] | None = None,
) -> str | None:
    """Pick an NPC's flee destination by rule.

    Towards home (the first hop of the route home) when that is a neighbour;
    otherwise away from enemies — the neighbour where the fewest known enemies
    are — preferring the quicker edge, then the id, for determinism.
    """
    options = list(destinations)
    if not options:
        return None
    if home_first_hop is not None and any(d.id == home_first_hop for d in options):
        return home_first_hop
    presence = enemy_presence or {}
    best = min(options, key=lambda d: (presence.get(d.id, 0), d.travel_seconds, d.id))
    return best.id
