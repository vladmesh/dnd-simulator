"""Entities layer — all tracked creatures: player, NPCs, named monsters.

Includes attack resolution (via CombatManager), initiative/combat management,
event perception, and visibility filtering. Manages CombatState per location.
Proximity-based activation: update_activation() marks creatures near players as
active and others as dormant; NPCs are moved to their scheduled location on
activation. Activation also rolls location encounter tables (cooldown-gated
and time-of-day filtered) to spawn transient monsters. Npc is a pure data model (role, personality, schedule, memory,
ai_type); decision-making is delegated to the brain field on Creature. NpcMemory
holds structured tags (NpcTag), recent events, inner state, and conversation
context. MemorySummarizer (in llm/) compresses events into memory after combat
ends. Direct access: get_entity, add_entity, remove_entity for hot controls.
"""

from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import (
    Npc,
    NpcActivity,
    ScheduleEntry,
    activity_flavor,
    hour_in_range,
    resolve_schedule,
)

__all__ = [
    "EntitiesLayer",
    "Npc",
    "NpcActivity",
    "ScheduleEntry",
    "activity_flavor",
    "hour_in_range",
    "resolve_schedule",
]
