"""LLM prompt builders for NPC dialog."""

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
