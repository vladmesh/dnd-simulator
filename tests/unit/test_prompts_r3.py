"""Context sections of the NPC peaceful and combat prompt builders."""

from __future__ import annotations

from typing import Any

from dnd_simulator.llm.prompts import build_npc_combat_prompt, build_npc_system_prompt


def _npc(inner_self: object = None) -> dict[str, Any]:
    return {
        "name": "Guard",
        "role": "guard",
        "personality": "  Alert.  ",
        "activity": "working",
        "location_label": "gate",
        "inner_self": inner_self,
    }


def _peaceful(**extra: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "time": {"hour": 10, "day": 1, "month": 1, "year": 1},
        "weather": {"condition": "light_rain", "temperature": 12},
        "location": {"name": "Square"},
        "settlements": [],
        "territory": "",
        "nation": {},
    }
    base.update(extra)
    return base


def _combat(**extra: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "self_hp": 10,
        "self_max_hp": 10,
        "self_weapon": "sword",
        "self_weapon_damage": "1d8",
    }
    base.update(extra)
    return base


class TestPeacefulPrompt:
    def test_inventory_listed(self) -> None:
        prompt = build_npc_system_prompt(
            _npc(), _peaceful(available_items=[{"id": "p1", "name": "Potion", "description": "Heals"}])
        )
        assert "Your inventory:" in prompt
        assert "  - Potion: Heals (id: p1)" in prompt

    def test_no_inventory_section_without_items(self) -> None:
        assert "Your inventory:" not in build_npc_system_prompt(_npc(), _peaceful())

    def test_weather_underscores_replaced(self) -> None:
        assert "light rain" in build_npc_system_prompt(_npc(), _peaceful())

    def test_nearby_entities_listed(self) -> None:
        prompt = build_npc_system_prompt(_npc(), _peaceful(), [{"id": "h1", "description": "a hero"}])
        assert "  - a hero (id: h1)" in prompt


class TestCombatPrompt:
    def test_nearby_without_distance_has_plain_line(self) -> None:
        prompt = build_npc_combat_prompt(_npc(), _combat(nearby=[{"id": "g1", "description": "goblin"}]))
        assert "Around you:\n- goblin (id: g1)\n" in prompt

    def test_nearby_with_distance_and_reach(self) -> None:
        prompt = build_npc_combat_prompt(
            _npc(),
            _combat(
                nearby=[{"id": "g1", "description": "goblin", "distance_ft": 5, "direction": "N", "reachable": True}]
            ),
        )
        assert "- goblin (id: g1) — 5 ft N (in reach this turn)" in prompt

    def test_nobody_around(self) -> None:
        assert "Nobody around." in build_npc_combat_prompt(_npc(), _combat())

    def test_walls_and_map_sections(self) -> None:
        prompt = build_npc_combat_prompt(_npc(), _combat(walls=["(0,0)-(5,0)"], battle_map_ascii="#.."))
        assert "Walls in the arena:\n- (0,0)-(5,0)\n" in prompt
        assert "Battle map:\n#..\n" in prompt

    def test_no_walls_or_map_sections_by_default(self) -> None:
        prompt = build_npc_combat_prompt(_npc(), _combat())
        assert "Walls in the arena:" not in prompt
        assert "Battle map:" not in prompt
        assert "Round 1." in prompt

    def test_inventory_listed(self) -> None:
        prompt = build_npc_combat_prompt(
            _npc(), _combat(available_items=[{"id": "p1", "name": "Potion", "description": "Heals"}])
        )
        assert "Your inventory:\n- Potion: Heals (id: p1)\n" in prompt

    def test_unarmed_with_weapon_in_inventory_hints_equip(self) -> None:
        prompt = build_npc_combat_prompt(
            _npc(),
            _combat(
                self_weapon="fists",
                available_items=[{"id": "s1", "name": "Sword", "description": "A sharp Weapon"}],
            ),
        )
        assert "fighting UNARMED" in prompt

    def test_armed_gets_no_unarmed_hint(self) -> None:
        prompt = build_npc_combat_prompt(
            _npc(), _combat(available_items=[{"id": "s1", "name": "Sword", "description": "weapon"}])
        )
        assert "fighting UNARMED" not in prompt

    def test_conditions_and_round_number(self) -> None:
        prompt = build_npc_combat_prompt(_npc(), _combat(self_conditions=["poisoned", "prone"], round_number=3))
        assert "Active effects: poisoned, prone" in prompt
        assert "Round 3." in prompt

    def test_movement_defaults_to_speed(self) -> None:
        prompt = build_npc_combat_prompt(_npc(), _combat(self_speed=25))
        assert "Movement remaining this turn: 25 ft" in prompt


class TestInnerSelfGoals:
    def test_freeform_goal_rendered(self) -> None:
        prompt = build_npc_combat_prompt(_npc({"goals": [{"text": "Find my brother", "status": "active"}]}), _combat())
        assert "Goals:" in prompt
        assert "- Find my brother (active)" in prompt

    def test_malformed_goals_skipped(self) -> None:
        prompt = build_npc_combat_prompt(
            _npc({"goals": ["not a dict", {"type": "kill", "target_id": "orc"}, {"text": "", "status": "active"}]}),
            _combat(),
        )
        assert "Goals:" not in prompt

    def test_non_dict_inner_self_ignored(self) -> None:
        prompt = build_npc_combat_prompt(_npc("garbage"), _combat())
        assert "Goals:" not in prompt
        assert "Relationships:" not in prompt
