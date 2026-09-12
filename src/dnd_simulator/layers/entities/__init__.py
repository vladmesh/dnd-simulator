"""Entities layer — all tracked creatures: player, NPCs, named monsters.

Includes attack resolution (via CombatManager), initiative/combat management,
event perception, and visibility filtering. Manages CombatState per location.
AwarenessBuilder assembles the PeacefulAwareness/CombatAwareness a brain sees,
querying lower layers for the surroundings the creature can perceive.
Anchor-based activation: update_activation() marks creatures near awake anchors as
active and others as dormant; it completes or interrupts persisted wait/sleep/travel
intents, while NPCs are moved to their scheduled location on
activation. Activation also rolls location encounter tables (cooldown-gated
and time-of-day filtered) to spawn transient monsters. Npc is a pure data model
(role, personality, schedule, inner self, ai_type); decision-making is delegated to
the brain field on Creature. InnerSelf holds typed state plus a journal, thoughts,
conversation context, and a persisted structured perception buffer. Active core-bearers
append visible events without affecting brain cursors. One digest entry point consumes
that buffer at combat end, active → dormant, intent completion/interruption, and capacity;
the current body delegates to MemorySummarizer (in llm/) for NPC journals.
Direct access: get_entity, add_entity, remove_entity for hot controls.
Save format is defined by Pydantic models in save_models.py (EntitiesState:
discriminated entity union, combat state incl. sides, layer RNG state);
entity_serialization.py builds them directly from live objects.
TriggerIndex and TriggerRuntime apply typed paired on/until activation conditions;
GM overrides are persisted alongside automatic activation state.
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
