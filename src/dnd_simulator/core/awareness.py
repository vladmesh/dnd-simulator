"""Structured awareness data passed to Brain.choose_action.

EntitiesLayer builds these from query_fn + internal state, so brains
never touch World directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dnd_simulator.core.models import EventType

if TYPE_CHECKING:
    from dnd_simulator.core.turn_budget import TurnBudget


@dataclass(frozen=True)
class NearbyEntity:
    """An entity visible to the observer (peaceful context)."""

    id: str
    description: str
    is_wounded: bool = False


@dataclass(frozen=True)
class CombatEntity:
    """An entity visible in combat — includes distance and direction."""

    id: str
    description: str
    is_wounded: bool = False
    distance_ft: int = 0
    direction: str = ""


@dataclass
class PeacefulAwareness:
    """What a creature knows in peacetime — weather, location, politics, nearby entities."""

    hour: int
    day: int
    month: int
    year: int
    weather: dict[str, object]
    location_name: str
    region_name: str
    settlements: list[dict[str, object]] | None
    territory_owner: str | None
    nation_info: dict[str, object] | None
    nearby: list[NearbyEntity] = field(default_factory=list)
    turn_budget: TurnBudget | None = None


@dataclass
class CombatAwareness:
    """What a creature knows in combat — stats, enemies, terrain."""

    self_hp: int
    self_max_hp: int
    self_ac: int
    self_speed: int
    self_weapon: str
    self_weapon_damage: str
    nearby: list[CombatEntity] = field(default_factory=list)
    round_number: int = 1
    walls: list[str] = field(default_factory=list)
    turn_budget: TurnBudget | None = None


@dataclass(frozen=True)
class PerceivedEvent:
    """A game event as perceived by a specific observer."""

    description: str
    event_type: EventType
    actor_id: str | None = None
    target_id: str | None = None
    data: dict[str, object] = field(default_factory=dict)
