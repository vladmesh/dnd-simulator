"""Diplomacy subsystem — war declarations, peace treaties, trade agreements."""

from __future__ import annotations

import random

from dnd_simulator.core.models import Event, EventType
from dnd_simulator.layers.politics.models import DiplomaticStatus, LeaderTrait, Nation
from dnd_simulator.rules.politics import peace_chance, trade_agreement_chance, war_declaration_chance


def _relation_key(a: str, b: str) -> tuple[str, str]:
    """Canonical key for a pair of nations (sorted)."""
    return (min(a, b), max(a, b))


def _nations_are_neighbors(
    nid_a: str,
    nid_b: str,
    nations: dict[str, Nation],
    region_adjacency: dict[str, list[str]],
) -> bool:
    """Check if two nations share a border."""
    nation_a = nations.get(nid_a)
    nation_b = nations.get(nid_b)
    if not nation_a or not nation_b:
        return False

    b_regions = set(nation_b.regions)
    for rid in nation_a.regions:
        neighbors = region_adjacency.get(rid, [])
        if any(n in b_regions for n in neighbors):
            return True
    return False


def process_diplomacy(
    nations: dict[str, Nation],
    relations: dict[tuple[str, str], DiplomaticStatus],
    war_durations: dict[tuple[str, str], int],
    region_adjacency: dict[str, list[str]],
    rng: random.Random,
) -> list[Event]:
    """Check for new wars, peace treaties, trade agreements. Mutates relations in place."""
    events: list[Event] = []
    nation_ids = list(nations.keys())

    for i, nid_a in enumerate(nation_ids):
        for nid_b in nation_ids[i + 1 :]:
            nation_a = nations[nid_a]
            nation_b = nations[nid_b]
            key = _relation_key(nid_a, nid_b)
            status = relations.get(key, DiplomaticStatus.PEACE)

            if not _nations_are_neighbors(nid_a, nid_b, nations, region_adjacency):
                continue

            if status == DiplomaticStatus.WAR:
                months = war_durations.get(key, 0)
                if rng.random() < peace_chance(months):
                    relations[key] = DiplomaticStatus.PEACE
                    war_durations.pop(key, None)
                    events.append(
                        Event(
                            event_type=EventType.CUSTOM,
                            source_layer="politics",
                            data={"type": "peace", "nation_a": nid_a, "nation_b": nid_b},
                            description=f"{nation_a.name} and {nation_b.name} sign a peace treaty",
                        )
                    )

            elif status == DiplomaticStatus.PEACE:
                # War declaration check (both directions)
                for aggressor, target in [(nation_a, nation_b), (nation_b, nation_a)]:
                    chance = war_declaration_chance(
                        aggressor.military,
                        target.military,
                        aggressor.leader.trait.value if aggressor.leader else None,
                    )
                    if rng.random() < chance:
                        relations[key] = DiplomaticStatus.WAR
                        war_durations[key] = 0
                        events.append(
                            Event(
                                event_type=EventType.CUSTOM,
                                source_layer="politics",
                                data={"type": "war_declared", "aggressor": aggressor.id, "target": target.id},
                                description=f"{aggressor.name} declares war on {target.name}!",
                            ),
                        )
                        break

                # Trade agreement check (if still at peace)
                if relations.get(key) == DiplomaticStatus.PEACE:
                    for n in [nation_a, nation_b]:
                        if (
                            n.leader
                            and n.leader.trait in (LeaderTrait.MERCHANT, LeaderTrait.DIPLOMAT)
                            and rng.random() < trade_agreement_chance()
                        ):
                            relations[key] = DiplomaticStatus.TRADE_AGREEMENT
                            events.append(
                                Event(
                                    event_type=EventType.CUSTOM,
                                    source_layer="politics",
                                    data={"type": "trade_agreement", "nation_a": nid_a, "nation_b": nid_b},
                                    description=f"{nation_a.name} and {nation_b.name} sign a trade agreement",
                                )
                            )
                            break

    return events
