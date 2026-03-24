"""Location graph — the world's navigation structure.

Every place in the world is a Location node. Edges connect neighboring
locations with distances in meters.  Region and settlement are tags on
a location, used to look up weather, terrain, politics, and economy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LocationEdge:
    """A weighted edge between two locations."""

    target_id: str
    distance_m: int  # meters


@dataclass(frozen=True)
class Location:
    """A node in the world graph."""

    id: str
    name: str
    region_id: str  # tag — for weather/terrain/politics lookups
    settlement_id: str = ""  # tag — for economy/npc binding
    edges: tuple[LocationEdge, ...] = ()
    description: str = ""


class LocationGraph:
    """Flat graph of all locations in the world.

    Pure data + lookup.  No tick, no events — just structure.
    """

    def __init__(self, locations: list[Location] | None = None) -> None:
        self._locations: dict[str, Location] = {}
        if locations:
            for loc in locations:
                self._locations[loc.id] = loc

    def get(self, location_id: str) -> Location:
        """Get a location by ID.  Raises KeyError if not found."""
        if location_id not in self._locations:
            raise KeyError(f"Location '{location_id}' not found")
        return self._locations[location_id]

    def neighbors(self, location_id: str) -> tuple[LocationEdge, ...]:
        """Return edges from a location."""
        return self.get(location_id).edges

    def region_of(self, location_id: str) -> str:
        """Shortcut: get the region tag for a location."""
        return self.get(location_id).region_id

    def has(self, location_id: str) -> bool:
        """Check if a location exists."""
        return location_id in self._locations

    def all_ids(self) -> list[str]:
        """Return all location IDs."""
        return list(self._locations.keys())

    def edge_between(self, from_id: str, to_id: str) -> LocationEdge | None:
        """Get the direct edge between two locations, or None."""
        for edge in self.get(from_id).edges:
            if edge.target_id == to_id:
                return edge
        return None

    def travel_seconds(self, from_id: str, to_id: str, speed_kmh: float = 5.0) -> int:
        """Calculate travel time in seconds for a direct edge.

        Raises ValueError if no direct edge exists.
        """
        edge = self.edge_between(from_id, to_id)
        if edge is None:
            raise ValueError(f"No direct path from '{from_id}' to '{to_id}'")
        distance_km = edge.distance_m / 1000.0
        hours = distance_km / speed_kmh
        return max(60, int(hours * 3600))  # minimum 1 minute
