"""Squad model - abstract mobile group in the living world."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SquadType(Enum):
    """What kind of group this is."""

    PATROL = "patrol"
    BANDIT = "bandit"
    CARAVAN = "caravan"
    MONSTER_PACK = "monster_pack"
    WAR_PARTY = "war_party"


class SquadBehavior(Enum):
    """How the squad moves and acts."""

    PATROL = "patrol"
    ROAM = "roam"
    GUARD = "guard"
    TRADE = "trade"
    HUNT = "hunt"
    RAID = "raid"


@dataclass
class Squad:
    """An abstract group that moves, fights by formulas, and materializes into Creatures near active characters."""

    id: str
    name: str
    faction_id: str
    squad_type: SquadType
    behavior: SquadBehavior
    current_location_id: str
    route: list[str]  # ordered location IDs for PATROL/TRADE
    territory: list[str]  # location IDs for ROAM/HUNT
    strength: int  # abstract power (not HP)
    max_strength: int
    member_templates: list[str]  # MonsterTemplate IDs
    tick_interval: int  # seconds between movement ticks
