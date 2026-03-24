"""Tool schemas for NPC actions via LLM tool use.

Each ActionType has a registered schema. Tools are built dynamically from
the available_actions list — no hardcoded tool sets.
"""

from __future__ import annotations

from typing import Any

from dnd_simulator.core.action import ActionType

# ---------------------------------------------------------------------------
# Tool schema registry: ActionType → OpenAI function-calling schema
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS: dict[ActionType, dict[str, Any]] = {
    ActionType.SAY: {
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
    ActionType.IDLE: {
        "type": "function",
        "function": {
            "name": "idle",
            "description": "Do nothing this turn. Use when there is nothing meaningful to do.",
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
    ActionType.ATTACK: {
        "type": "function",
        "function": {
            "name": "attack",
            "description": (
                "Attack a target with your equipped weapon (or fists if unarmed). Target must be within weapon reach."
            ),
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
    ActionType.DODGE: {
        "type": "function",
        "function": {
            "name": "dodge",
            "description": (
                "Take a defensive stance. Attacks against you have disadvantage until your next turn. Costs 1 action."
            ),
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
    ActionType.FLEE: {
        "type": "function",
        "function": {
            "name": "flee",
            "description": "Try to escape from combat. Costs 1 action.",
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
    ActionType.MOVE: {
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
    ActionType.DASH: {
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
    ActionType.USE_ITEM: {
        "type": "function",
        "function": {
            "name": "use_item",
            "description": (
                "Use a consumable item from your inventory (potion, scroll, etc.). Costs 1 action. Item is consumed."
            ),
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
    },
    ActionType.BLESS: {
        "type": "function",
        "function": {
            "name": "bless",
            "description": (
                "Invoke a blessing from your weapon. Costs a bonus action. "
                "Grants +d4 to all your attack rolls for several rounds."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    ActionType.EQUIP: {
        "type": "function",
        "function": {
            "name": "equip",
            "description": (
                "Equip a weapon from your inventory. Free action. "
                "Attacking with a weapon deals more damage than fists. "
                "Your current weapon (if any) goes back to inventory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "weapon_id": {
                        "type": "string",
                        "description": "ID of the weapon to equip (from available_items in your awareness)",
                    },
                },
                "required": ["weapon_id"],
            },
        },
    },
    ActionType.UNEQUIP: {
        "type": "function",
        "function": {
            "name": "unequip",
            "description": "Put away your equipped weapon. Free action. You will fight with fists.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
}


def get_tools(available_actions: list[ActionType]) -> list[dict[str, Any]]:
    """Build tool list from available actions. Only returns schemas for known types."""
    return [_TOOL_SCHEMAS[at] for at in available_actions if at in _TOOL_SCHEMAS]


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
