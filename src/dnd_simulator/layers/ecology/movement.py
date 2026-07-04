"""Squad movement over the location graph — split out of EcologyLayer (politics pattern).

Pure-ish functions taking the squad plus the layer's route-tracking dicts; they mutate the
squad's ``current_location_id`` and the route indices in place and return ``(from, to)`` or None.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from dnd_simulator.core.squad import Squad, SquadBehavior

if TYPE_CHECKING:
    from dnd_simulator.core.location import LocationGraph

# Behaviors that follow a fixed route.
_ROUTE_BEHAVIORS = {SquadBehavior.PATROL, SquadBehavior.TRADE}

# Behaviors that roam randomly within territory.
_ROAM_BEHAVIORS = {SquadBehavior.ROAM, SquadBehavior.HUNT, SquadBehavior.RAID}


def move_squad(
    squad: Squad,
    route_index: dict[str, int],
    route_direction: dict[str, int],
    location_graph: LocationGraph | None,
) -> tuple[str, str] | None:
    """Move a squad according to its behavior. Returns (from, to) or None if no move."""
    if squad.behavior is SquadBehavior.GUARD:
        return None
    if squad.behavior in _ROUTE_BEHAVIORS:
        return _move_route(squad, route_index, route_direction)
    if squad.behavior in _ROAM_BEHAVIORS:
        return _move_roam(squad, location_graph)
    return None


def _move_route(squad: Squad, route_index: dict[str, int], route_direction: dict[str, int]) -> tuple[str, str] | None:
    """Move along route, reversing at endpoints."""
    if not squad.route:
        return None

    # Initialize route tracking
    if squad.id not in route_index:
        try:
            route_index[squad.id] = squad.route.index(squad.current_location_id)
        except ValueError:
            route_index[squad.id] = 0
        route_direction[squad.id] = 1

    idx = route_index[squad.id]
    direction = route_direction[squad.id]
    next_idx = idx + direction

    # Reverse at endpoints
    if next_idx < 0 or next_idx >= len(squad.route):
        direction = -direction
        route_direction[squad.id] = direction
        next_idx = idx + direction

    if next_idx < 0 or next_idx >= len(squad.route):
        return None  # single-location route

    old = squad.current_location_id
    route_index[squad.id] = next_idx
    squad.current_location_id = squad.route[next_idx]
    return (old, squad.current_location_id)


def _move_roam(squad: Squad, location_graph: LocationGraph | None) -> tuple[str, str] | None:
    """Move to a random neighbor within territory."""
    if location_graph is None:
        return None

    edges = location_graph.neighbors(squad.current_location_id)
    candidates = [e.target_id for e in edges if e.target_id in squad.territory]
    if not candidates:
        return None

    old = squad.current_location_id
    squad.current_location_id = random.choice(candidates)
    return (old, squad.current_location_id)
