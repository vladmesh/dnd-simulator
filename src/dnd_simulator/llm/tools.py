"""Tool schemas for NPC actions via LLM tool use."""

from __future__ import annotations

from typing import Any

from dnd_simulator.core.character import Attack


def _attack_enum(attacks: tuple[Attack, ...]) -> list[str]:
    return [a.name for a in attacks]


def build_npc_tools(attacks: tuple[Attack, ...]) -> list[dict[str, Any]]:
    """Build OpenAI-compatible tool definitions for an NPC's available actions."""
    tools: list[dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "say",
                "description": "Say something out loud. Use for dialog, greetings, threats, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "What to say (in character, in Russian)",
                        },
                    },
                    "required": ["text"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "idle",
                "description": "Do nothing this turn. Use when there is no reason to act or speak.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
    ]

    if attacks:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "attack",
                    "description": "Attack a target with a weapon or ability.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_id": {
                                "type": "string",
                                "description": "ID of the target entity",
                            },
                            "weapon": {
                                "type": "string",
                                "enum": _attack_enum(attacks),
                                "description": "Which attack to use",
                            },
                        },
                        "required": ["target_id", "weapon"],
                    },
                },
            }
        )

    return tools
