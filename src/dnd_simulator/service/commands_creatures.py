from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.models import Query
from dnd_simulator.i18n import _
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
        answer = session.world.query_layer("entities", Query(question="all_creatures", params=params))
        result: list[dict[str, object]] = answer.value
        return result

    def get_creature_info(self, session_id: str, entity_id: str) -> dict[str, object]:
        """Get single entity detail."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        answer = session.world.query_layer("entities", Query(question="entity_info", params={"entity_id": entity_id}))
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
        self._get_entities_layer(session).add_entity(entity)
        return entity

    # -- Patch --

    def patch_creature(self, session_id: str, entity_id: str, updates: dict[str, Any]) -> None:
        """Update mutable creature fields. Applies only fields that exist on the entity type."""
        from dnd_simulator.core.character import Character, Creature
        from dnd_simulator.core.player import PlayerCharacter
        from dnd_simulator.layers.entities.models import Npc

        session = self._get_session(session_id)  # type: ignore[attr-defined]
        entity = self._get_entities_layer(session).get_entity(entity_id)
        if entity is None:
            raise ValueError(f"Creature '{entity_id}' not found")
        if isinstance(entity, PlayerCharacter):
            raise ValueError(_("Cannot edit player character from master panel"))
        if not isinstance(entity, Creature):
            raise ValueError(f"Entity '{entity_id}' is not a creature")

        # Creature-level fields
        if "current_hp" in updates:
            entity.current_hp = int(updates["current_hp"])
        if "ac" in updates:
            entity.ac = int(updates["ac"])
        if "location_id" in updates:
            entity.location_id = str(updates["location_id"])

        # Character-level fields
        if isinstance(entity, Character) and "gold" in updates:
            entity.gold = int(updates["gold"])

        # NPC-level fields
        if isinstance(entity, Npc) and "personality" in updates:
            entity.personality = str(updates["personality"])

    # -- Delete --

    def remove_creature(self, session_id: str, entity_id: str) -> None:
        """Remove a creature from a live session."""
        from dnd_simulator.core.player import PlayerCharacter

        session = self._get_session(session_id)  # type: ignore[attr-defined]
        layer = self._get_entities_layer(session)
        entity = layer.get_entity(entity_id)
        if entity is None:
            raise ValueError(f"Creature '{entity_id}' not found")
        if isinstance(entity, PlayerCharacter):
            raise ValueError(_("Cannot remove player character from master panel"))
        layer.remove_entity(entity_id)

    # -- Brain --

    def set_creature_brain(self, session_id: str, entity_id: str, brain_type: str, model: str = "") -> None:
        """Switch creature brain (rule_based or llm)."""
        from dnd_simulator.core.brain import RuleBrain
        from dnd_simulator.core.character import Creature
        from dnd_simulator.core.player import PlayerCharacter
        from dnd_simulator.layers.entities.models import Npc

        session = self._get_session(session_id)  # type: ignore[attr-defined]
        entity = self._get_entities_layer(session).get_entity(entity_id)
        if entity is None or not isinstance(entity, Creature):
            raise ValueError(f"Creature '{entity_id}' not found")
        if isinstance(entity, PlayerCharacter):
            raise ValueError(_("Cannot change player brain from master panel"))

        if brain_type == "rule_based":
            entity.brain = RuleBrain()
            if isinstance(entity, Npc):
                entity.ai_type = "rule_based"
        elif brain_type == "llm":
            if not self._llm:  # type: ignore[attr-defined]
                raise ValueError(_("LLM not configured"))
            from dnd_simulator.llm.brain import LlmBrain

            entity.brain = LlmBrain(self._llm)  # type: ignore[attr-defined]
            if isinstance(entity, Npc):
                entity.ai_type = "llm"
        else:
            raise ValueError(f"Unknown brain type: {brain_type}")


def _parse_spawn(data: dict[str, Any], known_locations: set[str] | None = None) -> Entity:
    """Create the right entity type based on entity_type field."""
    entity_type = str(data.get("entity_type", "npc"))

    if entity_type == "npc":
        from dnd_simulator.content_loader import parse_npc

        return parse_npc(str(data["id"]), data, known_locations=known_locations)

    # Monster / generic creature
    from dnd_simulator.content_loader import parse_ability_scores, parse_attacks
    from dnd_simulator.core.brain import RuleBrain
    from dnd_simulator.core.character import Creature

    max_hp = int(data.get("hp", 10))
    attacks = parse_attacks(data.get("attacks") or [])
    location_id = str(data.get("start_location", data.get("region_id", "")))

    creature = Creature(
        id=str(data["id"]),
        name=str(data["name"]),
        location_id=location_id,
        max_hp=max_hp,
        current_hp=max_hp,
        ac=int(data.get("ac", 10)),
        speed=int(data.get("speed", 30)),
        attacks=attacks,
        ability_scores=parse_ability_scores(data),
    )
    creature.brain = RuleBrain()
    return creature
