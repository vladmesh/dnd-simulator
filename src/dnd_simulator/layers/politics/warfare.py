"""Warfare subsystem — conquest resolution, military strength, region capture."""

from __future__ import annotations

import random

from dnd_simulator.core.events import RegionConqueredPayload
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.layers.politics.models import DiplomaticStatus, Nation
from dnd_simulator.rules.politics import calculate_war_strength, clamp

STALEMATE_THRESHOLD = 5.0
STALEMATE_MILITARY_COST = 1.0
WINNER_MILITARY_COST = 2.0
LOSER_MILITARY_COST = 4.0
LOSER_STABILITY_COST = 3.0


def _find_border_region(
    winner_id: str,
    loser_id: str,
    nations: dict[str, Nation],
    region_adjacency: dict[str, list[str]],
) -> str | None:
    """Find a loser's region adjacent to any winner's region."""
    winner = nations.get(winner_id)
    loser = nations.get(loser_id)
    if not winner or not loser:
        return None

    winner_regions = set(winner.regions)
    for rid in loser.regions:
        neighbors = region_adjacency.get(rid, [])
        if any(n in winner_regions for n in neighbors):
            return rid
    return None


def process_wars(
    nations: dict[str, Nation],
    relations: dict[tuple[str, str], DiplomaticStatus],
    war_durations: dict[tuple[str, str], int],
    region_adjacency: dict[str, list[str]],
    rng: random.Random,
) -> list[Event]:
    """Resolve active wars — winner takes a border region. Mutates nations in place."""
    events: list[Event] = []

    for key, status in list(relations.items()):
        if status != DiplomaticStatus.WAR:
            continue

        nation_a = nations.get(key[0])
        nation_b = nations.get(key[1])
        if not nation_a or not nation_b:
            continue

        strength_a = calculate_war_strength(nation_a.military, nation_a.stability, rng.random())
        strength_b = calculate_war_strength(nation_b.military, nation_b.stability, rng.random())

        if abs(strength_a - strength_b) < STALEMATE_THRESHOLD:
            nation_a.military = clamp(nation_a.military - STALEMATE_MILITARY_COST)
            nation_b.military = clamp(nation_b.military - STALEMATE_MILITARY_COST)
            continue

        winner, loser = (nation_a, nation_b) if strength_a > strength_b else (nation_b, nation_a)

        border_region = _find_border_region(winner.id, loser.id, nations, region_adjacency)
        if border_region:
            loser.regions.remove(border_region)
            winner.regions.append(border_region)
            events.append(
                Event(
                    event_type=EventType.REGION_CONQUERED,
                    source_layer="politics",
                    data=RegionConqueredPayload(winner.id, loser.id, border_region),
                    description=f"{winner.name} conquers {border_region} from {loser.name}",
                )
            )

        winner.military = clamp(winner.military - WINNER_MILITARY_COST)
        loser.military = clamp(loser.military - LOSER_MILITARY_COST)
        loser.stability = clamp(loser.stability - LOSER_STABILITY_COST)

    return events
