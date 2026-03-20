"""Entities layer — all tracked creatures: player, NPCs, named monsters.

Includes attack resolution, event perception, and visibility filtering.
"""

from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import (
    DEFAULT_SCHEDULES,
    Npc,
    NpcActivity,
    ScheduleEntry,
    hour_in_range,
)

__all__ = ["DEFAULT_SCHEDULES", "EntitiesLayer", "Npc", "NpcActivity", "ScheduleEntry", "hour_in_range"]
