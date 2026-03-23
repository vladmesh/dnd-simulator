"""Tool schemas for NPC actions via LLM tool use."""

from __future__ import annotations

from typing import Any


def _use_item_tool() -> dict[str, Any]:
    """Tool schema for using an inventory item."""
    return {
        "type": "function",
        "function": {
            "name": "use_item",
            "description": "Use an item from your inventory (potion, scroll, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "ID of the item to use (from available_items in awareness)",
                    },
                },
                "required": ["item_id"],
            },
        },
    }


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

    tools.append(_use_item_tool())

    return tools


def build_npc_combat_tools() -> list[dict[str, Any]]:
    """Build tool definitions for NPC combat actions — no say, focused on fighting."""
    return [
        _use_item_tool(),
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
                "name": "move",
                "description": (
                    "Move up to your speed (in feet). Use toward/away_from with a target ID, "
                    "or direction (north/south/east/west/northeast/northwest/southeast/southwest)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "toward": {
                            "type": "string",
                            "description": "ID of entity to move toward",
                        },
                        "away_from": {
                            "type": "string",
                            "description": "ID of entity to move away from",
                        },
                        "direction": {
                            "type": "string",
                            "description": "Compass direction: north, south, east, west, northeast, etc.",
                        },
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
                "name": "dash",
                "description": (
                    "Sprint: move up to DOUBLE your speed. Uses your action — you cannot attack this turn. "
                    "Same parameters as move."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "toward": {
                            "type": "string",
                            "description": "ID of entity to dash toward",
                        },
                        "away_from": {
                            "type": "string",
                            "description": "ID of entity to dash away from",
                        },
                        "direction": {
                            "type": "string",
                            "description": "Compass direction: north, south, east, west, northeast, etc.",
                        },
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
