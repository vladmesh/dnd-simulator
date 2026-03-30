"""LLM-powered brain for NPCs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.action import SKIP, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger
from dnd_simulator.i18n import _
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.llm.prompts import build_npc_combat_prompt, build_npc_system_prompt
from dnd_simulator.llm.tools import build_npc_combat_tools, build_npc_tools, get_reaction_tools, get_tools

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature

logger = structlog.get_logger(domain="llm.brain")

_MAX_RETRIES = 3


class LlmBrain(Brain):
    """Brain that uses an LLM to decide NPC actions via tool use."""

    def __init__(self, llm: LlmClient) -> None:
        self._llm = llm

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        from dnd_simulator.core.character import Character

        if not isinstance(creature, Character):
            return Action(name=ActionType.IDLE)

        is_combat = isinstance(awareness, CombatAwareness)
        logger.info("npc_turn_start", npc=creature.name, mode="combat" if is_combat else "peaceful")

        npc_data = creature.get_npc_data()

        # Enrich NPC data with schedule-dependent fields
        from dnd_simulator.layers.entities.models import Npc as NpcModel

        if isinstance(creature, NpcModel) and isinstance(awareness, PeacefulAwareness):
            npc_data["activity"] = creature.scheduled_activity(awareness.hour).value
            npc_data["location_label"] = awareness.location_name
        else:
            npc_data.setdefault("activity", "idle")
            npc_data.setdefault("location_label", "")

        if is_combat:
            assert isinstance(awareness, CombatAwareness)
            # Convert CombatAwareness to dict for prompt builder
            combat_dict = _combat_awareness_to_dict(awareness)
            system_prompt = build_npc_combat_prompt(npc_data, combat_dict)
            tools = build_npc_combat_tools()
            retry_hint = _("You must choose an action: attack, move, dash, dodge, flee, or idle.")
        else:
            assert isinstance(awareness, PeacefulAwareness)
            awareness_dict = _peaceful_awareness_to_dict(awareness)
            nearby_list: list[dict[str, str]] = [{"id": e.id, "description": e.description} for e in awareness.nearby]
            system_prompt = build_npc_system_prompt(npc_data, awareness_dict, nearby_list)
            tools = build_npc_tools()
            retry_hint = _("You must choose an action: say, attack, or idle.")

        # Use available_actions directly to build tools (dynamic, includes weapon-granted actions)
        if awareness.available_actions:
            tools = get_tools(awareness.available_actions)

        recent_events: list[str] = [e.description for e in events[-15:]]

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
                return Action(name=ActionType(tc.name), params=dict(tc.arguments))
            # No tool call — ask LLM to retry
            messages.append({"role": "assistant", "content": response.text or ""})
            messages.append({"role": "user", "content": retry_hint})

        # Exhausted retries — idle as fallback
        return Action(name=ActionType.IDLE)

    def choose_reaction(
        self,
        creature: Creature,
        trigger: ReactionTrigger,
        options: list[ReactionOption],
    ) -> Action:
        """Ask LLM whether to use a reaction. Single call, no retry."""
        tools = get_reaction_tools(options)
        if not tools:
            return SKIP

        trigger_desc = _("A creature is {trigger_type}. You can react or skip.").format(
            trigger_type=trigger.trigger_type.value.replace("_", " "),
        )
        messages: list[dict[str, object]] = [
            {"role": "system", "content": _("You are an NPC deciding whether to use your reaction.")},
            {"role": "user", "content": trigger_desc},
        ]

        response = self._llm.generate_with_tools(messages, tools)
        if response.is_tool_call:
            assert response.tool_call is not None
            tc = response.tool_call
            return Action(name=ActionType(tc.name), params=dict(tc.arguments))
        return SKIP


def _peaceful_awareness_to_dict(aw: PeacefulAwareness) -> dict[str, object]:
    """Convert PeacefulAwareness to dict format expected by prompt builders."""
    items_list: list[dict[str, str]] = [
        {"id": i.id, "name": i.name, "description": i.description} for i in aw.available_items
    ]
    return {
        "time": {"hour": aw.hour, "day": aw.day, "month": aw.month, "year": aw.year},
        "weather": aw.weather,
        "location": {"name": aw.region_name},
        "settlements": aw.settlements,
        "territory": aw.territory_owner,
        "nation": aw.nation_info,
        "available_items": items_list,
    }


def _combat_awareness_to_dict(aw: CombatAwareness) -> dict[str, object]:
    """Convert CombatAwareness to dict format expected by prompt builders."""
    nearby_list: list[dict[str, object]] = []
    for e in aw.nearby:
        entry: dict[str, object] = {"id": e.id, "description": e.description}
        if e.is_wounded:
            entry["is_wounded"] = True
        if e.distance_ft:
            entry["distance_ft"] = e.distance_ft
        if e.direction:
            entry["direction"] = e.direction
        nearby_list.append(entry)
    items_list: list[dict[str, str]] = [
        {"id": i.id, "name": i.name, "description": i.description} for i in aw.available_items
    ]
    return {
        "self_hp": aw.self_hp,
        "self_max_hp": aw.self_max_hp,
        "self_ac": aw.self_ac,
        "self_speed": aw.self_speed,
        "self_weapon": aw.self_weapon,
        "self_weapon_damage": aw.self_weapon_damage,
        "self_conditions": [c.value for c in aw.self_conditions],
        "nearby": nearby_list,
        "round_number": aw.round_number,
        "walls": aw.walls,
        "battle_map_ascii": aw.battle_map_ascii,
        "available_items": items_list,
    }
