"""LLM prompt builders for NPC dialog."""

from __future__ import annotations

from typing import Any


def build_npc_system_prompt(npc_data: dict[str, Any], awareness: dict[str, Any]) -> str:
    """Build a system prompt for an NPC based on personality and world state."""
    t = awareness["time"]
    w = awareness["weather"]
    loc = awareness["location"]

    # Nation context
    nation_ctx = ""
    if awareness["nation"]:
        n = awareness["nation"]
        leader = n.get("leader")
        leader_str = f"{leader['name']} ({leader['trait']})" if leader else "unknown"
        nation_ctx = (
            f"\nThis region belongs to {n['name']}."
            f" Leader: {leader_str}."
            f" The nation's wealth is {'high' if n['wealth'] > 60 else 'low' if n['wealth'] < 30 else 'moderate'},"
            f" military strength is {'strong' if n['military'] > 60 else 'weak' if n['military'] < 30 else 'moderate'},"
            f" and stability is {'high' if n['stability'] > 60 else 'low' if n['stability'] < 30 else 'moderate'}."
        )
    else:
        nation_ctx = "\nThis region is independent - no nation controls it."

    # Settlements context
    settlement_lines = ""
    if awareness["settlements"]:
        names = [f"{s['name']} ({s['type']})" for s in awareness["settlements"]]
        settlement_lines = f"\nSettlements here: {', '.join(names)}."

    # Previous conversation
    conv_ctx = ""
    if npc_data.get("conversation_summary"):
        conv_ctx = f"\n\nYou have spoken with this adventurer before: {npc_data['conversation_summary']}"

    weather_desc = w["condition"].replace("_", " ")

    return (
        f"You are {npc_data['name']}, a {npc_data['role']} in {loc['name']}.\n"
        f"\n"
        f"Personality: {npc_data['personality'].strip()}\n"
        f"\n"
        f"Current situation:\n"
        f"- Time: {t['hour']:02d}:00, Day {t['day']}, Month {t['month']}, Year {t['year']}\n"
        f"- Weather: {weather_desc}, {w['temperature']}\u00b0C\n"
        f"- You are currently {npc_data['activity']} at the {npc_data['location_label']}"
        f"{nation_ctx}"
        f"{settlement_lines}"
        f"{conv_ctx}\n"
        f"\n"
        f"Rules:\n"
        f"- Stay in character at all times\n"
        f"- Keep responses short (1-3 sentences)\n"
        f"- Speak naturally as a medieval fantasy character\n"
        f"- You only know about your own region, not distant lands\n"
        f"- Never break the fourth wall\n"
        f"- Always respond in Russian\n"
        f"- Your DEFAULT action is idle() — do nothing\n"
        f"- Only use say() when you have a reason to speak: someone addressed you,\n"
        f"  something important happened, or you need to react to a threat\n"
        f"- Do NOT speak just because it is your turn — silence is normal\n"
        f"- Use attack() only if you have a strong in-character reason to fight"
    )
