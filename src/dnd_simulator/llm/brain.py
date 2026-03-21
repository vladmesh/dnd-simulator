"""LLM-powered brain for NPCs — extracts decision logic from the old Npc.take_turn."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dnd_simulator.core.action import Action
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Character, build_awareness, build_combat_awareness
from dnd_simulator.core.models import Query
from dnd_simulator.i18n import _
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.llm.prompts import build_npc_combat_prompt, build_npc_system_prompt
from dnd_simulator.llm.tools import build_npc_combat_tools, build_npc_tools

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.world import World

logger = logging.getLogger("dnd_simulator.npc")

_MAX_RETRIES = 3


class LlmBrain(Brain):
    """Brain that uses an LLM to decide NPC actions via tool use."""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def choose_action(self, creature: Creature, world: World) -> Action:
        if not isinstance(creature, Character):
            return Action(name="idle")

        logger.info("[NPC:%s] === starts turn (%s) ===", creature.name, "combat" if creature.in_combat else "peace")

        npc_data = creature.get_npc_data()

        # Enrich NPC data with schedule-dependent fields
        from dnd_simulator.layers.entities.models import Npc as NpcModel

        if isinstance(creature, NpcModel):
            hour = world.time.hour
            npc_data["activity"] = creature.scheduled_activity(hour).value
            try:
                loc = world.location_graph.get(creature.current_location(hour))
                npc_data["location_label"] = loc.name
            except (KeyError, AttributeError):
                npc_data["location_label"] = creature.location_id
        else:
            npc_data.setdefault("activity", "idle")
            npc_data.setdefault("location_label", creature.location_id)

        if creature.in_combat:
            combat_awareness = build_combat_awareness(world, creature)
            system_prompt = build_npc_combat_prompt(npc_data, combat_awareness)
            tools = build_npc_combat_tools()
            retry_hint = _("You must choose an action: attack, move, dash, dodge, flee, or idle.")
        else:
            awareness = build_awareness(world, creature.location_id)
            entities_answer = world.query_layer(
                "entities", Query(question="entities_at_location", params={"location_id": creature.location_id})
            )
            nearby: list[dict[str, str]] = []
            for e in entities_answer.value:
                if e["id"] != creature.id:
                    desc = creature.perceive_by_id(e["id"], world)
                    nearby.append({"id": str(e["id"]), "description": desc})
            system_prompt = build_npc_system_prompt(npc_data, awareness, nearby)
            tools = build_npc_tools()
            retry_hint = _("You must choose an action: say, attack, or idle.")

        # Get only new events since last turn (delta, not full log)
        log_answer = world.query_layer(
            "entities", Query(question="new_perceived_events", params={"entity_id": creature.id})
        )
        recent_events: list[str] = log_answer.value[-15:] if log_answer.value else []

        turn_prompt = _("Your turn. Choose an action.")
        if recent_events:
            events_text = "\n".join(f"- {e}" for e in recent_events)
            turn_prompt = _("What happened since your last turn:\n{events}\n\nYour turn. Choose an action.").format(
                events=events_text
            )

        messages: list[dict[str, object]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": turn_prompt},
        ]

        for _attempt in range(_MAX_RETRIES):
            response = self._llm.generate_with_tools(messages, tools)
            if response.is_tool_call:
                assert response.tool_call is not None
                tc = response.tool_call
                return Action(name=tc.name, params=dict(tc.arguments))
            # No tool call — ask LLM to retry
            messages.append({"role": "assistant", "content": response.text or ""})
            messages.append({"role": "user", "content": retry_hint})

        # Exhausted retries — idle as fallback
        return Action(name="idle")
