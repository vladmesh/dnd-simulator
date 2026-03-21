from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.models import Query
from dnd_simulator.service.session import GameSession

if TYPE_CHECKING:
    from dnd_simulator.layers.entities.layer import EntitiesLayer
    from dnd_simulator.layers.entities.models import Npc


class NpcCommands:
    """Mixin: NPC management commands (master hot controls)."""

    def _get_entities_layer(self, session: GameSession) -> EntitiesLayer:
        raise NotImplementedError

    def list_npcs(self, session_id: str) -> list[dict[str, object]]:
        """List all active NPCs in a session."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        answer = session.world.query_layer("entities", Query(question="all_npcs", params={}))
        result: list[dict[str, object]] = answer.value
        return result

    def get_npc_info(self, session_id: str, npc_id: str) -> dict[str, object]:
        """Get single NPC detail."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        answer = session.world.query_layer("entities", Query(question="npc_info", params={"npc_id": npc_id}))
        result: dict[str, object] = answer.value
        return result

    def spawn_npc(self, session_id: str, npc_data: dict[str, Any]) -> Npc:
        """Spawn an NPC into a live session."""
        from dnd_simulator.content_loader import parse_npc
        from dnd_simulator.layers.entities.models import Npc as NpcModel

        session = self._get_session(session_id)  # type: ignore[attr-defined]
        npc = parse_npc(str(npc_data["id"]), npc_data)
        self._get_entities_layer(session).add_entity(npc)
        assert isinstance(npc, NpcModel)
        return npc

    def remove_npc(self, session_id: str, npc_id: str) -> None:
        """Remove an NPC from a live session."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        layer = self._get_entities_layer(session)
        entity = layer.get_entity(npc_id)
        if entity is None:
            raise ValueError(f"NPC '{npc_id}' not found")
        layer.remove_entity(npc_id)

    def patch_npc(self, session_id: str, npc_id: str, updates: dict[str, Any]) -> None:
        """Update mutable NPC fields in a live session."""
        from dnd_simulator.layers.entities.models import Npc as NpcModel

        session = self._get_session(session_id)  # type: ignore[attr-defined]
        entity = self._get_entities_layer(session).get_entity(npc_id)
        if entity is None or not isinstance(entity, NpcModel):
            raise ValueError(f"NPC '{npc_id}' not found")

        if "current_hp" in updates:
            entity.current_hp = int(updates["current_hp"])
        if "ac" in updates:
            entity.ac = int(updates["ac"])
        if "personality" in updates:
            entity.personality = str(updates["personality"])
        if "location_id" in updates:
            entity.location_id = str(updates["location_id"])
        if "gold" in updates:
            entity.gold = int(updates["gold"])

    def set_npc_brain(self, session_id: str, npc_id: str, brain_type: str, model: str = "") -> None:
        """Switch NPC brain (rule_based or llm)."""
        from dnd_simulator.core.brain import RuleBrain
        from dnd_simulator.layers.entities.models import Npc as NpcModel

        session = self._get_session(session_id)  # type: ignore[attr-defined]
        entity = self._get_entities_layer(session).get_entity(npc_id)
        if entity is None or not isinstance(entity, NpcModel):
            raise ValueError(f"NPC '{npc_id}' not found")

        if brain_type == "rule_based":
            entity.brain = RuleBrain()
            entity.ai_type = "rule_based"
        elif brain_type == "llm":
            if not self._llm:  # type: ignore[attr-defined]
                raise ValueError("LLM not configured")
            from dnd_simulator.llm.brain import LlmBrain

            entity.brain = LlmBrain(self._llm)  # type: ignore[attr-defined]
            entity.ai_type = "llm"
        else:
            raise ValueError(f"Unknown brain type: {brain_type}")
