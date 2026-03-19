"""Base character model and world awareness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dnd_simulator.core.models import Query
from dnd_simulator.core.world import World


@dataclass
class Character:
    """Any entity that exists in the world and can act."""

    id: str
    name: str
    region_id: str


def build_awareness(world: World, region_id: str) -> dict[str, Any]:
    """Gather what a character in a region knows about the world."""
    time = world.time

    weather = world.query_layer("geography", Query(question="weather", params={"region_id": region_id}))
    region = world.query_layer("geography", Query(question="region_info", params={"region_id": region_id}))
    settlements = world.query_layer(
        "settlements", Query(question="region_settlements", params={"region_id": region_id})
    )
    owner = world.query_layer("politics", Query(question="region_owner", params={"region_id": region_id}))

    nation_info = None
    if owner.value:
        nation_info = world.query_layer("politics", Query(question="nation_info", params={"nation_id": owner.value}))

    return {
        "time": {
            "hour": time.hour,
            "day": time.day,
            "month": time.month,
            "year": time.year,
        },
        "weather": weather.value,
        "location": region.value,
        "settlements": settlements.value,
        "territory": owner.value,
        "nation": nation_info.value if nation_info else None,
    }
