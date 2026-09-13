"""Decision prompts expose selected personal state without raw save data."""

from __future__ import annotations

from dnd_simulator.llm.prompts import build_npc_combat_prompt, build_npc_system_prompt


def _npc_data(inner_self: object) -> dict[str, object]:
    return {
        "name": "Guard",
        "role": "guard",
        "personality": "Alert.",
        "activity": "working",
        "location_label": "gate",
        "inner_self": inner_self,
    }


def _inner_self() -> dict[str, object]:
    return {
        "relations": [{"target_id": "hero", "type": "trusts", "intensity": 70}],
        "mood": "alerted",
        "goals": [{"type": "protect", "target_id": "gate", "status": "active"}],
        "alignment": {"law_chaos": 2, "good_evil": -1},
        "journal": "The gate was threatened yesterday.",
        "thoughts": ["Keep watch."],
        "current_conversation": "secret",
        "perceived_event_buffer": [{"description": "hidden"}],
    }


def _peaceful_awareness() -> dict[str, object]:
    return {
        "time": {"hour": 10, "day": 1, "month": 1, "year": 1},
        "weather": {"condition": "clear", "temperature": 20},
        "location": {"name": "Square"},
        "settlements": [],
        "territory": "",
        "nation": {},
    }


def _combat_awareness() -> dict[str, object]:
    return {
        "self_hp": 10,
        "self_max_hp": 10,
        "self_ac": 12,
        "self_speed": 30,
        "self_weapon": "sword",
        "self_weapon_damage": "1d8",
    }


def test_peaceful_and_combat_prompts_render_explicit_personal_sections() -> None:
    for prompt in (
        build_npc_system_prompt(_npc_data(_inner_self()), _peaceful_awareness()),
        build_npc_combat_prompt(_npc_data(_inner_self()), _combat_awareness()),
    ):
        assert "Relationships:" in prompt
        assert "hero: trusts (70)" in prompt
        assert "Mood: alerted" in prompt
        assert "Goals:" in prompt and "protect gate (active)" in prompt
        assert "Journal:" in prompt and "Recent thoughts:" in prompt
        assert "perceived_event_buffer" not in prompt
        assert "current_conversation" not in prompt
        assert '"alignment"' not in prompt


def test_empty_inner_self_omits_personal_sections() -> None:
    prompt = build_npc_system_prompt(_npc_data({"mood": "neutral"}), _peaceful_awareness())

    assert "Relationships:" not in prompt
    assert "Mood:" not in prompt
    assert "Goals:" not in prompt
    assert "Journal:" not in prompt
    assert "Recent thoughts:" not in prompt
