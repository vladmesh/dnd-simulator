"""Tool schemas for NPC actions via LLM tool use.

Schemas are auto-generated from the ActionDef registry — no hand-written
tool definitions. Descriptions come from ``ActionDef.llm_hint`` (if set)
or ``ActionDef.description``.
"""

from __future__ import annotations

from typing import Any

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.action_defs import ActionDef, get_action_def

# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------


def _build_schema(d: ActionDef) -> dict[str, Any]:
    """Build an OpenAI function-calling schema from an ActionDef."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for p in d.params:
        properties[p.name] = {"type": p.param_type, "description": p.description}
        if p.required:
            required.append(p.name)

    desc = d.llm_hint or d.description
    schema: dict[str, Any] = {
        "type": "function",
        "function": {
            "name": d.action_type.value,
            "description": desc,
            "parameters": {"type": "object", "properties": properties},
        },
    }
    if required:
        schema["function"]["parameters"]["required"] = required
    return schema


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_tools(available_actions: list[ActionType]) -> list[dict[str, Any]]:
    """Build tool list from available actions. Internal actions are excluded."""
    return [_build_schema(get_action_def(at)) for at in available_actions if not get_action_def(at).internal]


# Legacy API — used by LlmBrain when available_actions is empty (shouldn't happen in practice)
def build_npc_tools() -> list[dict[str, Any]]:
    """Fallback: static peaceful tool set."""
    return get_tools([ActionType.SAY, ActionType.IDLE, ActionType.ATTACK, ActionType.USE_ITEM])


def build_npc_combat_tools() -> list[dict[str, Any]]:
    """Fallback: static combat tool set."""
    return get_tools(
        [
            ActionType.USE_ITEM,
            ActionType.ATTACK,
            ActionType.DODGE,
            ActionType.FLEE,
            ActionType.MOVE,
            ActionType.DASH,
            ActionType.IDLE,
        ]
    )
