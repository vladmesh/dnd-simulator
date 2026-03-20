"""Entities layer — all tracked creatures: player, NPCs, named monsters.

Includes attack resolution, initiative/combat management, event perception,
and visibility filtering. Manages CombatState per region.
Npc is a pure data model (personality, schedule, ai_type); decision-making
is delegated to the brain field on Creature.
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
