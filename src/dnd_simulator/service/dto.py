"""Service-layer DTOs — typed return objects passed from GameService to adapters.

Adapters translate these into HTTP response models; service methods never
construct response schemas directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResourcePoolView:
    """A single resource pool, flattened for the adapter."""

    id: str
    max_uses: int
    current_uses: int


@dataclass(frozen=True)
class JourneyView:
    """Resolved presentation of a persisted travel intent."""

    destination_id: str
    destination_name: str
    current_location_name: str
    next_location_name: str
    remaining_route: tuple[str, ...]
    next_arrival_seconds: int


@dataclass(frozen=True)
class PlayerStatusData:
    """Full player status snapshot — derived stats already computed."""

    player_id: str
    name: str
    race: str
    char_class: str
    level: int
    experience: int
    level_up_available: bool
    xp_to_next_level: int
    alignment: str
    hp: int
    max_hp: int
    ac: int
    gold: int
    location_id: str
    appearance: str
    ability_scores: dict[str, int]
    journey: JourneyView | None = None
    resource_pools: list[ResourcePoolView] = field(default_factory=list)
    equipped: list[dict[str, object]] = field(default_factory=list)
    inventory: list[dict[str, object]] = field(default_factory=list)
