"""LLM prompt builders for NPC dialog and combat."""

from __future__ import annotations

from typing import Any


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
        leader_str = f"{leader['name']} ({leader['trait']})" if leader else "неизвестен"
        nation_ctx = f"\nТерритория: {n['name']}. Правитель: {leader_str}."
    else:
        nation_ctx = "\nНезависимая территория."

    # Settlements context
    settlement_lines = ""
    if awareness["settlements"]:
        names = [f"{s['name']} ({s['type']})" for s in awareness["settlements"]]
        settlement_lines = f"\nПоселения: {', '.join(names)}."

    # Previous conversation
    conv_ctx = ""
    if npc_data.get("conversation_summary"):
        conv_ctx = f"\n\nТы уже общался с этим путником: {npc_data['conversation_summary']}"

    # Nearby entities
    entities_ctx = ""
    if nearby_entities:
        lines = []
        for e in nearby_entities:
            lines.append(f"  - {e['description']} (id: {e['id']})")
        entities_ctx = "\nРядом с тобой:\n" + "\n".join(lines)

    weather_desc = w["condition"].replace("_", " ")

    return (
        f"Ты — {npc_data['name']}, {npc_data['role']} в {loc['name']}.\n"
        f"\n"
        f"Характер: {npc_data['personality'].strip()}\n"
        f"\n"
        f"Обстановка:\n"
        f"- Время: {t['hour']:02d}:00, день {t['day']}, месяц {t['month']}, год {t['year']}\n"
        f"- Погода: {weather_desc}, {w['temperature']}°C\n"
        f"- Ты сейчас {npc_data['activity']}, находишься: {npc_data['location_label']}"
        f"{nation_ctx}"
        f"{settlement_lines}"
        f"{entities_ctx}"
        f"{conv_ctx}\n"
        f"\n"
        f"Правила:\n"
        f"- Отыгрывай персонажа, не выходи из роли\n"
        f"- Отвечай коротко (1-3 предложения)\n"
        f"- Говори как персонаж средневекового фэнтези\n"
        f"- Всегда отвечай на русском языке\n"
        f"- По умолчанию используй idle() — ничего не делать\n"
        f"- Используй say() только если есть причина говорить: кто-то обратился к тебе,\n"
        f"  произошло что-то важное, или нужно отреагировать на угрозу\n"
        f"- НЕ говори просто потому что наступил твой ход — молчание нормально\n"
        f"- Используй attack(target_id) только если у тебя есть веская причина драться.\n"
        f"  target_id — это id существа из списка рядом с тобой"
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

    hp_status = "здоров"
    if hp < max_hp // 2:
        hp_status = "тяжело ранен"
    elif hp < max_hp:
        hp_status = "ранен"

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

    entities_ctx = "\nВокруг тебя:\n" + "\n".join(entities_lines) if entities_lines else "\nВокруг никого нет."

    # Walls
    walls = combat_awareness.get("walls", [])
    walls_ctx = ""
    if walls:
        walls_lines = "\n".join(f"- {w}" for w in walls)
        walls_ctx = f"\nСтены на арене:\n{walls_lines}\n"

    round_num = combat_awareness.get("round_number", 1)

    return (
        f"Ты — {npc_data['name']}, {npc_data['role']}. Ты в бою!\n"
        f"\n"
        f"Характер: {npc_data['personality'].strip()}\n"
        f"\n"
        f"Твоё состояние:\n"
        f"- HP: {hp}/{max_hp} ({hp_status})\n"
        f"- Оружие: {weapon} ({weapon_dmg})\n"
        f"- Скорость: {speed} ft\n"
        f"{entities_ctx}"
        f"{walls_ctx}\n"
        f"Раунд {round_num}.\n"
        f"\n"
        f"Правила:\n"
        f"- Выбери одно действие: attack, dodge, move, dash, flee или idle\n"
        f"- attack(target_id) — ударить цель (должна быть в пределах досягаемости оружия)\n"
        f"- move(toward/away_from/direction) — переместиться на {speed} ft\n"
        f"- dash(toward/away_from/direction) — спринт на {speed * 2} ft (вместо атаки)\n"
        f"- Стены блокируют движение — нельзя пройти сквозь стену\n"
        f"- Хочешь что-то сказать — впиши в description\n"
        f"- Отвечай на русском языке"
    )
