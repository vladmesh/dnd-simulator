"""Entities layer — all tracked creatures: player, NPCs, named monsters.

Includes attack resolution (via CombatManager), initiative/combat management,
event perception, and visibility filtering. Manages CombatState per region.
Npc is a pure data model (personality, schedule, ai_type); decision-making
is delegated to the brain field on Creature. Direct access: get_entity,
add_entity, remove_entity for hot controls.
"""

from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import (
    DEFAULT_SCHEDULE_TEMPLATES,
    Npc,
    NpcActivity,
    ScheduleEntry,
    activity_flavor,
    hour_in_range,
    resolve_schedule,
)

__all__ = [
    "DEFAULT_SCHEDULE_TEMPLATES",
    "EntitiesLayer",
    "Npc",
    "NpcActivity",
    "ScheduleEntry",
    "activity_flavor",
    "hour_in_range",
    "resolve_schedule",
]
