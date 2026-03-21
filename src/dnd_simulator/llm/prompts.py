"""LLM prompt builders for NPC dialog and combat."""

from __future__ import annotations

import json
from typing import Any

from dnd_simulator.i18n import _


def build_npc_system_prompt(
    npc_data: dict[str, Any],
    awareness: dict[str, Any],
    nearby_entities: list[dict[str, str]] | None = None,
) -> str:
    """Build a system prompt for an NPC based on personality and world state."""
    t = awareness["time"]
    w = awareness["weather"]
    loc = awareness["location"]

    # Nation context
    nation_ctx = ""
    if awareness["nation"]:
        n = awareness["nation"]
        leader = n.get("leader")
        leader_str = f"{leader['name']} ({leader['trait']})" if leader else _("unknown")
        nation_ctx = "\n" + _("Territory: {nation}. Ruler: {leader}.").format(nation=n["name"], leader=leader_str)
    else:
        nation_ctx = "\n" + _("Independent territory.")

    # Settlements context
    settlement_lines = ""
    if awareness["settlements"]:
        names = [f"{s['name']} ({s['type']})" for s in awareness["settlements"]]
        settlement_lines = "\n" + _("Settlements: {names}").format(names=", ".join(names))

    # NPC memory
    memory_ctx = ""
    memory = npc_data.get("memory")
    if memory and any(memory.get(k) for k in ("tags", "recent", "inner_state", "current_conversation")):
        memory_ctx = "\n\n" + _("Your memory:") + "\n" + json.dumps(memory, ensure_ascii=False, indent=2)

    # Nearby entities
    entities_ctx = ""
    if nearby_entities:
        lines = []
        for e in nearby_entities:
            lines.append(f"  - {e['description']} (id: {e['id']})")
        entities_ctx = "\n" + _("Near you:") + "\n" + "\n".join(lines)

    weather_desc = w["condition"].replace("_", " ")

    rules = _(
        "Rules:\n"
        "- Stay in character, do not break role\n"
        "- Answer briefly (1-3 sentences)\n"
        "- Speak as a medieval fantasy character\n"
        "- Always respond in the game language\n"
        "- By default use idle() — do nothing\n"
        "- Use say() only if there is a reason to speak: someone addressed you,\n"
        "  something important happened, or you need to react to a threat\n"
        "- Do NOT speak just because it is your turn — silence is normal\n"
        "- Use attack(target_id) only if you have a good reason to fight.\n"
        "  target_id is the id of a creature from the nearby list"
    )

    return (
        _("You are {name}, {role} in {location}.").format(
            name=npc_data["name"], role=npc_data["role"], location=loc["name"]
        )
        + "\n"
        "\n" + _("Personality:") + f" {npc_data['personality'].strip()}\n"
        f"\n"
        + _("Setting:")
        + "\n"
        + "- "
        + _("Time: {hour}:00, day {day}, month {month}, year {year}").format(
            hour=f"{t['hour']:02d}", day=t["day"], month=t["month"], year=t["year"]
        )
        + "\n"
        + "- "
        + _("Weather: {condition}, {temperature}C").format(condition=weather_desc, temperature=w["temperature"])
        + "\n"
        + "- "
        + _("You are currently {activity}, located at: {location}").format(
            activity=npc_data["activity"], location=npc_data["location_label"]
        )
        + f"{nation_ctx}"
        f"{settlement_lines}"
        f"{entities_ctx}"
        f"{memory_ctx}\n"
        f"\n" + rules
    )


def build_npc_combat_prompt(
    npc_data: dict[str, Any],
    combat_awareness: dict[str, Any],
) -> str:
    """Build a focused combat prompt for an NPC — no weather, politics, or schedules."""
    hp = combat_awareness["self_hp"]
    max_hp = combat_awareness["self_max_hp"]
    weapon = combat_awareness["self_weapon"]
    weapon_dmg = combat_awareness["self_weapon_damage"]
    speed = combat_awareness.get("self_speed", 30)

    hp_status = _("healthy")
    if hp < max_hp // 2:
        hp_status = _("badly wounded")
    elif hp < max_hp:
        hp_status = _("wounded")

    # Nearby entities with distances
    entities_lines: list[str] = []
    nearby = combat_awareness.get("nearby", [])
    for e in nearby:
        dist = e.get("distance_ft")
        direction = e.get("direction")
        if dist is not None and direction is not None:
            entities_lines.append(f"- {e['description']} (id: {e['id']}) — {dist} ft {direction}")
        else:
            entities_lines.append(f"- {e['description']} (id: {e['id']})")

    entities_ctx = (
        "\n" + _("Around you:") + "\n" + "\n".join(entities_lines) if entities_lines else "\n" + _("Nobody around.")
    )

    # Walls
    walls = combat_awareness.get("walls", [])
    walls_ctx = ""
    if walls:
        walls_lines = "\n".join(f"- {w}" for w in walls)
        walls_ctx = "\n" + _("Walls in the arena:") + f"\n{walls_lines}\n"

    round_num = combat_awareness.get("round_number", 1)

    combat_rules = _(
        "Rules:\n"
        "- Choose one action: attack, dodge, move, dash, flee, or idle\n"
        "- attack(target_id) — strike a target (must be within weapon reach)\n"
        "- move(toward/away_from/direction) — move up to {speed} ft\n"
        "- dash(toward/away_from/direction) — sprint up to {dash_speed} ft (instead of attacking)\n"
        "- Walls block movement — you cannot move through a wall\n"
        "- Want to say something — put it in description\n"
        "- Respond in the game language"
    ).format(speed=speed, dash_speed=speed * 2)

    return (
        _("You are {name}, {role}. You are in combat!").format(name=npc_data["name"], role=npc_data["role"]) + "\n"
        "\n" + _("Personality:") + f" {npc_data['personality'].strip()}\n"
        f"\n"
        + _("Your status:")
        + "\n"
        + "- "
        + _("HP: {hp}/{max_hp} ({status})").format(hp=hp, max_hp=max_hp, status=hp_status)
        + "\n"
        + "- "
        + _("Weapon: {weapon} ({dmg})").format(weapon=weapon, dmg=weapon_dmg)
        + "\n"
        + "- "
        + _("Speed: {speed} ft").format(speed=speed)
        + "\n"
        + f"{entities_ctx}"
        f"{walls_ctx}\n" + _("Round {num}.").format(num=round_num) + "\n"
        "\n" + combat_rules
    )
