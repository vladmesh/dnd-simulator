"""Lair model — a fixed place with a persistent monster population.

Unlike a Squad (abstract mobile group), a lair is stationary: it lives at one
location, has a fixed roster with an optional core/boss, and runs a state machine
(ACTIVE -> DEPLETED). Population respawn and depletion land in later tasks; this
module defines the data shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LairState(Enum):
    """Lifecycle of a lair. DEPLETED is terminal: no further respawn or spawn."""

    ACTIVE = "active"
    DEPLETED = "depleted"


@dataclass
class Lair:
    """A stationary monster home. Materializes its roster into Creatures near players."""

    id: str
    name: str
    faction_id: str
    location_id: str
    members: list[str]  # minion MonsterTemplate IDs (full roster)
    core: str | None = None  # core/boss MonsterTemplate ID; its death depletes the lair
    respawn_interval: int = 86400  # seconds of game time between respawns (default 1 day)
    depletion_chance: float = 0.0  # chance to deplete after a full wipe (coreless lairs)
    # -- mutable runtime state (persisted via EcologyLayer.get_state) --
    state: LairState = field(default=LairState.ACTIVE)
    alive_members: list[str] | None = None  # surviving minion templates; None == full roster
    core_alive: bool = True
    last_respawn_time: int = 0  # game-time seconds anchoring the respawn countdown (set on loss/respawn)
