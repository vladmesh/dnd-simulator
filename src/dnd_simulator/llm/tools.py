"""Tool schemas for NPC actions via LLM tool use.

Schemas are auto-generated from the ActionDef registry — no hand-written
tool definitions. Descriptions come from ``ActionDef.llm_hint`` (if set)
or ``ActionDef.description``.
"""

from __future__ import annotations

from openai.types.chat import ChatCompletionFunctionToolParam

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.action_defs import ActionDef, get_action_def
from dnd_simulator.core.reactions import ReactionOption

_THOUGHT_PROPERTY = {
    "type": "string",
    "description": "A short private inner thought, not speech. Do not include it in action parameters.",
}

# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------


def _function_tool(
    name: str, description: str, properties: dict[str, object], required: list[str]
) -> ChatCompletionFunctionToolParam:
    """One OpenAI function tool; ``thought`` is always offered as an optional private field."""
    if "thought" in properties:
        raise ValueError(f"tool parameter conflicts with reserved LLM field: {name}.thought")
    properties["thought"] = dict(_THOUGHT_PROPERTY)
    parameters: dict[str, object] = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


def _build_schema(d: ActionDef) -> ChatCompletionFunctionToolParam:
    """Build an OpenAI function-calling schema from an ActionDef."""
    properties: dict[str, object] = {}
    required: list[str] = []
    for p in d.params:
        properties[p.name] = {"type": p.param_type, "description": p.description}
        if p.required:
            required.append(p.name)
    return _function_tool(d.action_type.value, d.llm_hint or d.description, properties, required)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_tools(available_actions: list[ActionType]) -> list[ChatCompletionFunctionToolParam]:
    """Build tool list from available actions. Internal actions are excluded."""
    return [_build_schema(get_action_def(at)) for at in available_actions if not get_action_def(at).internal]


def get_reaction_tools(options: list[ReactionOption]) -> list[ChatCompletionFunctionToolParam]:
    """Build tool list from reaction options.

    Simpler than action tools — each option becomes a tool with its
    pre-built params as properties.
    """
    tools: list[ChatCompletionFunctionToolParam] = []
    for opt in options:
        properties: dict[str, object] = {}
        required: list[str] = []
        for key, value in opt.params.items():
            properties[key] = {"type": "string", "description": f"Value: {value}"}
            required.append(key)
        tools.append(_function_tool(opt.action_type.value, opt.description, properties, required))
    return tools


# Legacy API — used by LlmBrain when available_actions is empty (shouldn't happen in practice)
def build_npc_tools() -> list[ChatCompletionFunctionToolParam]:
    """Fallback: static peaceful tool set."""
    return get_tools([ActionType.SAY, ActionType.IDLE, ActionType.ATTACK, ActionType.USE_ITEM])


def build_npc_combat_tools() -> list[ChatCompletionFunctionToolParam]:
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
