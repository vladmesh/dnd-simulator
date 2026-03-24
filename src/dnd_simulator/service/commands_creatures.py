from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.models import Query, QueryType
from dnd_simulator.service.session import GameSession

if TYPE_CHECKING:
    from dnd_simulator.core.character import Entity
    from dnd_simulator.layers.entities.layer import EntitiesLayer


class CreatureCommands:
    """Mixin: creature management commands (master hot controls)."""

    def _get_entities_layer(self, session: GameSession) -> EntitiesLayer:
        raise NotImplementedError

    # -- List / Get --

    def list_creatures(
        self,
        session_id: str,
        entity_type: str | None = None,
        location_id: str | None = None,
        active: bool | None = None,
    ) -> list[dict[str, object]]:
        """List all creatures in a session with optional filters."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        params: dict[str, object] = {}
        if entity_type:
            params["entity_type"] = entity_type
        if location_id:
            params["location_id"] = location_id
        if active is not None:
            params["active"] = active
        answer = session.world.query_layer("entities", Query(question=QueryType.ALL_CREATURES, params=params))
        result: list[dict[str, object]] = answer.value
        return result

    def get_creature_info(self, session_id: str, entity_id: str) -> dict[str, object]:
        """Get single entity detail."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        answer = session.world.query_layer(
            "entities", Query(question=QueryType.ENTITY_INFO, params={"entity_id": entity_id})
        )
        result: dict[str, object] = answer.value
        return result

    # -- Spawn --

    def spawn_creature(self, session_id: str, data: dict[str, Any]) -> Entity:
        """Spawn a creature into a live session.

        entity_type in data determines what gets created:
        - "npc" → Npc (with role, personality, schedule, memory)
        - "monster" → Creature (bare creature with attacks)
        """
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        known_locations = set(session.world.location_graph.all_ids())
        entity = _parse_spawn(data, known_locations=known_locations)
        # Assign brain via factory
        from dnd_simulator.core.character import Creature
        from dnd_simulator.layers.entities.models import Npc

        if isinstance(entity, Npc):
            entity.brain = self._brain_factory.create(entity.ai_type)  # type: ignore[attr-defined]
        elif isinstance(entity, Creature):
            entity.brain = self._brain_factory.create(str(data.get("ai", "rule_based")))  # type: ignore[attr-defined]
        self._get_entities_layer(session).add_entity(entity)
        return entity

    # -- Patch --

    def patch_creature(self, session_id: str, entity_id: str, updates: dict[str, Any]) -> None:
        """Update mutable creature fields. Applies only fields that exist on the entity type."""
        from dnd_simulator.core.character import Character, Creature
        from dnd_simulator.layers.entities.models import Npc

        session = self._get_session(session_id)  # type: ignore[attr-defined]
        entity = self._get_entities_layer(session).get_entity(entity_id)
        if entity is None:
            raise ValueError(f"Creature '{entity_id}' not found")
        if not isinstance(entity, Creature):
            raise ValueError(f"Entity '{entity_id}' is not a creature")

        # Creature-level fields
        if "current_hp" in updates:
            entity.current_hp = int(updates["current_hp"])
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

        # Character-level fields
        if isinstance(entity, Character) and "gold" in updates:
            entity.gold = int(updates["gold"])

        # NPC-level fields
        if isinstance(entity, Npc) and "personality" in updates:
            entity.personality = str(updates["personality"])

    # -- Delete --

    def remove_creature(self, session_id: str, entity_id: str) -> None:
        """Remove a creature from a live session."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        layer = self._get_entities_layer(session)
        entity = layer.get_entity(entity_id)
        if entity is None:
            raise ValueError(f"Creature '{entity_id}' not found")
        layer.remove_entity(entity_id)

    # -- Items --

    def give_item(self, session_id: str, entity_id: str, item_data: dict[str, Any]) -> dict[str, str]:
        """Give an item to a creature. Auto-equips weapon if creature has none equipped."""
        from dnd_simulator.content_loader import parse_equipped_weapon, parse_items
        from dnd_simulator.core.character import Creature

        session = self._get_session(session_id)  # type: ignore[attr-defined]
        entity = self._get_entities_layer(session).get_entity(entity_id)
        if entity is None or not isinstance(entity, Creature):
            raise ValueError(f"Creature '{entity_id}' not found")

        items = parse_items([item_data])
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

    def set_creature_brain(self, session_id: str, entity_id: str, brain_type: str, model: str = "") -> None:
        """Switch creature brain (rule_based or llm)."""
        from dnd_simulator.core.character import Creature
        from dnd_simulator.layers.entities.models import Npc

        session = self._get_session(session_id)  # type: ignore[attr-defined]
        entity = self._get_entities_layer(session).get_entity(entity_id)
        if entity is None or not isinstance(entity, Creature):
            raise ValueError(f"Creature '{entity_id}' not found")
        entity.brain = self._brain_factory.create(brain_type, strict=True)  # type: ignore[attr-defined]
        if isinstance(entity, Npc):
            entity.ai_type = brain_type


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
    location_id = str(data.get("start_location") or data["region_id"])

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
