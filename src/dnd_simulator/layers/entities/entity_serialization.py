"""Entity save serialization — the get_state half, split out of EntitiesLayer.

Mirror of ``combat_serialization`` (which owns the combat-state half). The load/restore
half stays in ``EntitiesLayer.load_state`` because it dispatches entity construction against
the live layer. Item (de)serialization lives in ``content_loader`` (imported lazily here:
``content_loader.__init__`` pulls in this package, so a top-level import would cycle).
"""

from __future__ import annotations

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.container import Container
from dnd_simulator.core.models import EntityKind
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import Npc


def serialize_entity(entity: Entity) -> dict[str, object]:
    """Serialize a single entity to a save dict (inverse of the reconstruction in load_state)."""
    from dnd_simulator.content_loader.creatures import player_to_full_save_data
    from dnd_simulator.content_loader.items import EQUIPMENT_FIELDS, serialize_item

    e = entity
    data: dict[str, object] = {
        "id": e.id,
        "name": e.name,
        "location_id": e.location_id,
        "active": e.active,
    }
    if isinstance(e, Creature):
        # Structural fields needed to reconstruct spawned creatures from save data
        data.update(
            {
                "max_hp": e.max_hp,
                "ac": e.ac,
                "speed": e.speed,
                "ability_scores": e.ability_scores.to_dict(),
            }
        )
        if e.attacks:
            data["attacks"] = [
                {
                    "name": a.name,
                    "ability": a.ability.value,
                    "damage": [{"dice": d.dice, "type": d.type.value} for d in a.damage],
                    "reach": a.reach,
                }
                for a in e.attacks
            ]
        if e.wake_at_seconds is not None:
            data["wake_at_seconds"] = e.wake_at_seconds
        if e.conditions:
            data["conditions"] = {c.value: r for c, r in e.conditions.items()}
        if e.inventory:
            data["inventory"] = [serialize_item(item) for item in e.inventory]
        for field_name in EQUIPMENT_FIELDS:
            eq_item = getattr(e, field_name)
            if eq_item is not None:
                data[field_name] = serialize_item(eq_item)
        if e.reputation:
            data["reputation"] = dict(e.reputation)
        if e.resource_pools:
            data["resource_pools"] = [
                {
                    "id": pool.id,
                    "max_uses": pool.max_uses,
                    "current_uses": pool.current_uses,
                    "reset_on": pool.reset_on.value,
                }
                for pool in e.resource_pools
            ]
    if isinstance(e, PlayerCharacter):
        data["entity_type"] = EntityKind.PLAYER.value
        data.update(player_to_full_save_data(e))
    elif isinstance(e, Npc):
        data["entity_type"] = EntityKind.NPC.value
        data.update(
            {
                "current_hp": e.current_hp,
                "role": e.role.value,
                "personality": e.personality,
                "settlement_id": e.settlement_id,
                "location_override": e.location_override,
                "memory": e.memory.to_dict(),
                "ai_type": e.ai_type,
                # Aliases for parse_npc compatibility (used to reconstruct spawned NPCs)
                "hp": e.max_hp,
                "ai": e.ai_type,
                "start_location": e.location_id,
                "race": e.race.value,
                "class": e.char_class.value,
            }
        )
    elif isinstance(e, Creature):
        data["entity_type"] = EntityKind.CREATURE.value
        data["current_hp"] = e.current_hp
    elif isinstance(e, Container):
        data["entity_type"] = EntityKind.CONTAINER.value
        data["is_open"] = e.is_open
        data["gold"] = e.gold
        if e.inventory:
            data["inventory"] = [serialize_item(item) for item in e.inventory]
    return data
