from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.models import Query, QueryType
from dnd_simulator.service.base import GameServiceProtocol

if TYPE_CHECKING:
    from dnd_simulator.core.character import Entity


class CreatureCommands(GameServiceProtocol):
    """Mixin: creature management commands (master hot controls)."""

    # -- List / Get --

    def list_creatures(
        self,
        session_id: str,
        entity_type: str | None = None,
        location_id: str | None = None,
        active: bool | None = None,
    ) -> list[dict[str, object]]:
        """List all creatures in a session with optional filters."""
        session = self._get_session(session_id)
        params: dict[str, object] = {}
        if entity_type:
            params["entity_type"] = entity_type
        if location_id:
            params["location_id"] = location_id
        if active is not None:
            params["active"] = active
        answer = session.world.query_layer("entities", Query(question=QueryType.ALL_CREATURES, params=params))
        assert isinstance(answer.value, list)
        return answer.value

    def get_creature_info(self, session_id: str, entity_id: str) -> dict[str, object]:
        """Get single entity detail."""
        session = self._get_session(session_id)
        answer = session.world.query_layer(
            "entities", Query(question=QueryType.ENTITY_INFO, params={"entity_id": entity_id})
        )
        assert isinstance(answer.value, dict)
        return answer.value

    # -- Spawn --

    def spawn_creature(self, session_id: str, data: dict[str, Any]) -> Entity:
        """Spawn a creature into a live session.

        entity_type in data determines what gets created:
        - "npc" → Npc (with role, personality, schedule, memory)
        - "monster" → Creature (bare creature with attacks)
        """
        session = self._get_session(session_id)
        known_locations = set(session.world.location_graph.all_ids())
        entity = _parse_spawn(data, known_locations=known_locations)
        # Assign brain via factory
        from dnd_simulator.core.character import Creature
        from dnd_simulator.layers.entities.models import Npc

        if isinstance(entity, Npc):
            entity.brain = self._brain_factory.create(entity.ai_type)
        elif isinstance(entity, Creature):
            entity.brain = self._brain_factory.create(str(data.get("ai", "rule_based")))
        self._get_entities_layer(session).add_entity(entity)
        return entity

    # -- Patch --

    def patch_creature(self, session_id: str, entity_id: str, updates: dict[str, Any]) -> None:
        """Update mutable creature fields. Applies only fields that exist on the entity type."""
        from dnd_simulator.core.character import Character, Creature
        from dnd_simulator.layers.entities.models import Npc

        session = self._get_session(session_id)
        entity = self._get_entities_layer(session).get_entity(entity_id)
        if entity is None:
            raise ValueError(f"Creature '{entity_id}' not found")
        if not isinstance(entity, Creature):
            raise ValueError(f"Entity '{entity_id}' is not a creature")

        # Creature-level fields
        if "current_hp" in updates:
            entity.current_hp = int(updates["current_hp"])
        if "max_hp" in updates:
            entity.max_hp = int(updates["max_hp"])
        if "ac" in updates:
            entity.ac = int(updates["ac"])
        if "location_id" in updates:
            entity.location_id = str(updates["location_id"])
        if "conditions" in updates:
            raw = updates["conditions"]
            if isinstance(raw, dict):
                entity.conditions = {Condition(str(k)): int(v) if v is not None else None for k, v in raw.items()}
            else:
                entity.conditions = {Condition(str(c)): None for c in raw}

        # Resource pools — add or replace by id
        if "resource_pools" in updates:
            from dnd_simulator.core.resource import ResourcePool, RestType

            for pool_data in updates["resource_pools"]:
                pool = ResourcePool(
                    id=str(pool_data["id"]),
                    max_uses=int(pool_data["max_uses"]),
                    current_uses=int(pool_data["current_uses"]),
                    reset_on=RestType(str(pool_data["reset_on"])),
                )
                # Replace existing pool with same id, or append
                entity.resource_pools = [p for p in entity.resource_pools if p.id != pool.id]
                entity.resource_pools.append(pool)

        # Character-level fields
        if isinstance(entity, Character) and "gold" in updates:
            entity.gold = int(updates["gold"])

        # NPC-level fields
        if isinstance(entity, Npc) and "personality" in updates:
            entity.personality = str(updates["personality"])

    # -- Delete --

    def remove_creature(self, session_id: str, entity_id: str) -> None:
        """Remove a creature from a live session."""
        session = self._get_session(session_id)
        layer = self._get_entities_layer(session)
        entity = layer.get_entity(entity_id)
        if entity is None:
            raise ValueError(f"Creature '{entity_id}' not found")
        layer.remove_entity(entity_id)

    # -- Items --

    def give_item(self, session_id: str, entity_id: str, item_data: dict[str, Any]) -> dict[str, str]:
        """Give an item to a creature. Auto-equips weapon if creature has none equipped."""
        from dnd_simulator.content_loader import load_catalog, parse_equipped_weapon, parse_items
        from dnd_simulator.content_loader.schemas import ItemContent
        from dnd_simulator.core.character import Creature

        session = self._get_session(session_id)
        entity = self._get_entities_layer(session).get_entity(entity_id)
        if entity is None or not isinstance(entity, Creature):
            raise ValueError(f"Creature '{entity_id}' not found")

        content_dir: Path = self._content_dir  # type: ignore[attr-defined]
        item_catalog_dir = content_dir / "catalogs" / "items"
        item_catalog = load_catalog(item_catalog_dir, ItemContent) if item_catalog_dir.exists() else {}
        items = parse_items([item_data], item_catalog=item_catalog)
        item = items[0]
        entity.inventory.append(item)

        # Auto-equip first weapon if nothing equipped
        if entity.equipped_weapon is None:
            weapon = parse_equipped_weapon(entity.inventory)
            if weapon:
                entity.equipped_weapon = weapon
                entity.inventory = [i for i in entity.inventory if i.id != weapon.id]

        return {"item_id": item.id, "name": item.name}

    # -- Brain --

    def set_creature_brain(self, session_id: str, entity_id: str, brain_type: str, model: str = "") -> str:
        """Switch creature brain (rule_based or llm). Returns actual brain type set."""
        from dnd_simulator.core.character import Creature
        from dnd_simulator.layers.entities.models import Npc
        from dnd_simulator.llm.brain import LlmBrain

        session = self._get_session(session_id)
        entity = self._get_entities_layer(session).get_entity(entity_id)
        if entity is None or not isinstance(entity, Creature):
            raise ValueError(f"Creature '{entity_id}' not found")
        entity.brain = self._brain_factory.create(brain_type)
        actual_type = "llm" if isinstance(entity.brain, LlmBrain) else "rule_based"
        if isinstance(entity, Npc):
            entity.ai_type = actual_type
        return actual_type


def _parse_spawn(data: dict[str, Any], known_locations: set[str] | None = None) -> Entity:
    """Create the right entity type based on entity_type field."""
    entity_type = str(data.get("entity_type", "npc"))

    if entity_type == "npc":
        from dnd_simulator.content_loader import parse_npc

        return parse_npc(str(data["id"]), data, known_locations=known_locations)

    # Monster / generic creature
    from dnd_simulator.content_loader import parse_ability_scores, parse_attacks
    from dnd_simulator.core.character import Creature

    max_hp = int(data["hp"])
    attacks = parse_attacks(data.get("attacks") or [])
    location_id = str(data["start_location"])

    return Creature(
        id=str(data["id"]),
        name=str(data["name"]),
        location_id=location_id,
        max_hp=max_hp,
        current_hp=max_hp,
        ac=int(data["ac"]),
        speed=int(data["speed"]),
        attacks=attacks,
        ability_scores=parse_ability_scores(data),
    )
