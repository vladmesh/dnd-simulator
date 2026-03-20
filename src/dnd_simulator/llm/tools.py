"""Tool schemas for NPC actions via LLM tool use."""

from __future__ import annotations

from typing import Any


def build_npc_tools() -> list[dict[str, Any]]:
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

    tools.append(
        {
            "type": "function",
            "function": {
                "name": "attack",
                "description": "Attack a target with your equipped weapon (or fists if unarmed).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_id": {
                            "type": "string",
                            "description": "ID of the target entity",
                        },
                    },
                    "required": ["target_id"],
                },
            },
        }
    )

    return tools


def build_npc_combat_tools() -> list[dict[str, Any]]:
    """Build tool definitions for NPC combat actions — no say, focused on fighting."""
    return [
        {
            "type": "function",
            "function": {
                "name": "attack",
                "description": "Attack a target with your equipped weapon.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_id": {
                            "type": "string",
                            "description": "ID of the target entity",
                        },
                        "description": {
                            "type": "string",
                            "description": "Flavor text: what you say or how you attack (optional)",
                        },
                    },
                    "required": ["target_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "dodge",
                "description": "Take a defensive stance. Harder to hit this round.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Flavor text (optional)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "flee",
                "description": "Try to escape from combat.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Flavor text (optional)",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "idle",
                "description": "Do nothing this turn.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Flavor text (optional)",
                        },
                    },
                },
            },
        },
    ]
