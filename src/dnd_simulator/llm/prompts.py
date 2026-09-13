"""LLM prompt builders for NPC dialog and combat.

Prompts provide CONTEXT (who you are, what you see, status).
Actions are described by TOOL SCHEMAS — the prompt does not list them.
Only situational hints (e.g. "you are unarmed but have weapons") are added.
"""

from __future__ import annotations

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

    memory_ctx = _inner_self_context(npc_data.get("inner_self"))

    # Nearby entities
    entities_ctx = ""
    if nearby_entities:
        lines = []
        for e in nearby_entities:
            lines.append(f"  - {e['description']} (id: {e['id']})")
        entities_ctx = "\n" + _("Near you:") + "\n" + "\n".join(lines)

    # Inventory items
    items = awareness.get("available_items", [])
    items_ctx = ""
    if items:
        items_lines = "\n".join(f"  - {i['name']}: {i['description']} (id: {i['id']})" for i in items)
        items_ctx = "\n" + _("Your inventory:") + "\n" + items_lines

    weather_desc = w["condition"].replace("_", " ")

    rules = _(
        "Rules:\n"
        "- Stay in character, do not break role\n"
        "- Answer briefly (1-3 sentences)\n"
        "- Speak as a medieval fantasy character\n"
        "- Always respond in the game language\n"
        "- Choose one of the available tools. Default to idle if nothing to do\n"
        "- Do NOT speak just because it is your turn — silence is normal"
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
        f"{items_ctx}"
        f"{memory_ctx}\n"
        f"\n" + rules
    )


def build_npc_combat_prompt(
    npc_data: dict[str, Any],
    combat_awareness: dict[str, Any],
) -> str:
    """Build a focused combat prompt for an NPC — no weather, politics, or schedules.

    Action descriptions come from tool schemas, not this prompt.
    Only situational context and hints are included here.
    """
    hp = combat_awareness["self_hp"]
    max_hp = combat_awareness["self_max_hp"]
    weapon = combat_awareness["self_weapon"]
    weapon_dmg = combat_awareness["self_weapon_damage"]
    speed = combat_awareness.get("self_speed", 30)
    movement_remaining = combat_awareness.get("movement_remaining", speed)

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
            reach_tag = " " + _("(in reach this turn)") if e.get("reachable") else ""
            entities_lines.append(f"- {e['description']} (id: {e['id']}) — {dist} ft {direction}{reach_tag}")
        else:
            entities_lines.append(f"- {e['description']} (id: {e['id']})")

    entities_ctx = (
        "\n" + _("Around you:") + "\n" + "\n".join(entities_lines) if entities_lines else "\n" + _("Nobody around.")
    )

    # Active conditions on self
    conditions = combat_awareness.get("self_conditions", [])
    conditions_ctx = ""
    if conditions:
        conditions_ctx = "\n- " + _("Active effects: {effects}").format(effects=", ".join(conditions))

    # Walls
    walls = combat_awareness.get("walls", [])
    walls_ctx = ""
    if walls:
        walls_lines = "\n".join(f"- {w}" for w in walls)
        walls_ctx = "\n" + _("Walls in the arena:") + f"\n{walls_lines}\n"

    # Battle map ASCII
    battle_map = combat_awareness.get("battle_map_ascii", "")
    map_ctx = ""
    if battle_map:
        map_ctx = "\n" + _("Battle map:") + f"\n{battle_map}\n"

    round_num = combat_awareness.get("round_number", 1)

    # Inventory items
    items = combat_awareness.get("available_items", [])
    items_ctx = ""
    if items:
        items_lines = "\n".join(f"- {i['name']}: {i['description']} (id: {i['id']})" for i in items)
        items_ctx = "\n" + _("Your inventory:") + "\n" + items_lines + "\n"

    # Situational hints
    hints: list[str] = []
    if weapon == "fists" and any("weapon" in str(i.get("description", "")).lower() for i in items):
        hints.append(
            _(
                "IMPORTANT: You are fighting UNARMED (fists, 1 damage). "
                "You have weapons in your inventory! Use equip(weapon_id) — it's a FREE action."
            )
        )

    hints_ctx = ""
    if hints:
        hints_ctx = "\n" + "\n".join(hints) + "\n"

    memory_ctx = _inner_self_context(npc_data.get("inner_self"))

    rules = _(
        "Rules:\n"
        "- Choose one of the available tools\n"
        "- Walls block movement — you cannot move through a wall\n"
        "- Want to say something — put it in the description parameter of any action\n"
        "- Respond in the game language"
    )

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
        + "- "
        + _("Movement remaining this turn: {n} ft").format(n=movement_remaining)
        + f"{conditions_ctx}\n"
        + f"{entities_ctx}"
        f"{items_ctx}"
        f"{memory_ctx}"
        f"{hints_ctx}"
        f"{walls_ctx}"
        f"{map_ctx}\n" + _("Round {num}.").format(num=round_num) + "\n"
        "\n" + rules
    )


def _inner_self_context(value: object) -> str:
    """Render decision-relevant personal state without exposing raw persistence data."""
    if not isinstance(value, dict):
        return ""
    sections: list[str] = []

    relations = value.get("relations")
    if isinstance(relations, list) and relations:
        lines = []
        for relation in relations:
            if isinstance(relation, dict):
                target = relation.get("target_id")
                relation_type = relation.get("type")
                intensity = relation.get("intensity")
                if isinstance(target, str) and isinstance(relation_type, str) and isinstance(intensity, int):
                    lines.append(
                        _("- {target}: {kind} ({intensity})").format(
                            target=target, kind=relation_type, intensity=intensity
                        )
                    )
        if lines:
            sections.append(_("Relationships:") + "\n" + "\n".join(lines))

    mood = value.get("mood")
    if isinstance(mood, str) and mood != "neutral":
        sections.append(_("Mood: {mood}").format(mood=mood))

    goals = value.get("goals")
    if isinstance(goals, list) and goals:
        lines = []
        for goal in goals:
            if not isinstance(goal, dict):
                continue
            status = goal.get("status")
            if not isinstance(status, str):
                continue
            goal_type = goal.get("type")
            target = goal.get("target_id")
            text = goal.get("text")
            if isinstance(goal_type, str) and isinstance(target, str):
                lines.append(_("- {goal} {target} ({status})").format(goal=goal_type, target=target, status=status))
            elif isinstance(text, str) and text:
                lines.append(_("- {goal} ({status})").format(goal=text, status=status))
        if lines:
            sections.append(_("Goals:") + "\n" + "\n".join(lines))

    journal = value.get("journal")
    if isinstance(journal, str) and journal.strip():
        sections.append(_("Journal:") + "\n" + journal)

    thoughts = value.get("thoughts")
    if isinstance(thoughts, list):
        lines = [f"- {thought}" for thought in thoughts if isinstance(thought, str) and thought.strip()]
        if lines:
            sections.append(_("Recent thoughts:") + "\n" + "\n".join(lines))

    return "\n\n" + "\n\n".join(sections) if sections else ""
