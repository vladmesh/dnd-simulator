"""Abstract squad-vs-squad combat — split out of EcologyLayer (politics pattern).

Functions take the layer's squad + route-tracking dicts and mutate them in place
(strength updates, destroyed-squad cleanup, loser retreat).
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.events import SquadCombatPayload
from dnd_simulator.core.models import Event, EventType, FactionRelation
from dnd_simulator.core.queries import query_faction_relation
from dnd_simulator.core.squad import Squad
from dnd_simulator.rules.abstract_combat import TriggeredEncounter, resolve_abstract_combat

if TYPE_CHECKING:
    from dnd_simulator.core.location import LocationGraph
    from dnd_simulator.core.models import QueryFn

logger = structlog.get_logger(domain="ecology")

_SOURCE_LAYER = "ecology"


def resolve_squad_combat(
    squads: dict[str, Squad],
    location_graph: LocationGraph | None,
    last_move_time: dict[str, int],
    route_index: dict[str, int],
    route_direction: dict[str, int],
    query_fn: QueryFn,
    rng: random.Random,
) -> list[Event]:
    """Find hostile squads at the same location and resolve combat; remove destroyed squads."""
    events: list[Event] = []

    # Group squads by location
    by_location: dict[str, list[Squad]] = defaultdict(list)
    for squad in squads.values():
        by_location[squad.current_location_id].append(squad)

    # Check each location with multiple squads
    fought: set[str] = set()
    for location_id, located in by_location.items():
        if len(located) < 2:
            continue

        for i, a in enumerate(located):
            if a.id in fought:
                continue
            for b in located[i + 1 :]:
                if b.id in fought:
                    continue
                if not _are_hostile(a, b, query_fn):
                    continue

                events.append(_fight_squads(a, b, location_id, location_graph, rng))
                fought.add(a.id)
                fought.add(b.id)
                break  # each squad fights at most once per tick

    # Remove destroyed squads
    destroyed = [sid for sid, s in squads.items() if s.strength <= 0]
    for sid in destroyed:
        logger.info("squad_destroyed", squad_id=sid)
        del squads[sid]
        last_move_time.pop(sid, None)
        route_index.pop(sid, None)
        route_direction.pop(sid, None)

    return events


def _are_hostile(a: Squad, b: Squad, query_fn: QueryFn) -> bool:
    """Check if two squads are hostile via faction relations."""
    if a.faction_id == b.faction_id:
        return False
    return query_faction_relation(query_fn, a.faction_id, b.faction_id) is FactionRelation.HOSTILE


def _fight_squads(
    a: Squad,
    b: Squad,
    location_id: str,
    location_graph: LocationGraph | None,
    rng: random.Random,
) -> Event:
    """Resolve combat between two squads. Loser retreats."""
    # Model each squad as encounters for the other
    b_encounters = [TriggeredEncounter(cr=cr, count=1) for cr in b.member_crs] if b.member_crs else []
    a_encounters = [TriggeredEncounter(cr=cr, count=1) for cr in a.member_crs] if a.member_crs else []

    result_a = resolve_abstract_combat(a.strength, b_encounters)
    result_b = resolve_abstract_combat(b.strength, a_encounters)

    a.strength = max(0, a.strength - result_a.strength_lost)
    b.strength = max(0, b.strength - result_b.strength_lost)

    # Determine winner/loser
    if result_a.won:
        winner, loser = a, b
    else:
        winner, loser = b, a

    # Loser retreats to a random neighbor (if alive and graph available)
    if loser.strength > 0 and location_graph is not None:
        edges = location_graph.neighbors(location_id)
        if edges:
            loser.current_location_id = rng.choice(edges).target_id

    logger.info(
        "squad_combat",
        winner=winner.id,
        loser=loser.id,
        winner_strength=winner.strength,
        loser_strength=loser.strength,
    )

    return Event(
        event_type=EventType.SQUAD_COMBAT,
        source_layer=_SOURCE_LAYER,
        data=SquadCombatPayload(
            location_id,
            winner.id,
            winner.name,
            loser.id,
            loser.name,
            winner.strength,
            loser.strength,
        ),
        description=f"{winner.name} defeated {loser.name} at {location_id}",
    )
