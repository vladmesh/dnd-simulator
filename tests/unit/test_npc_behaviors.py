"""Tests for NPC behavior data loading from YAML."""

from __future__ import annotations

import inspect
from pathlib import Path

from dnd_simulator.core.character import NpcRole
from dnd_simulator.layers.entities.models import (
    NpcActivity,
    activity_flavor,
    canned_line,
    resolve_schedule,
)

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


class TestYamlFileExists:
    def test_npc_behaviors_yaml_exists(self) -> None:
        yaml_path = CONTENT_DIR / "npc_behaviors.yaml"
        assert yaml_path.exists(), f"Expected YAML at {yaml_path}"

    def test_models_py_has_no_inline_schedule_data(self) -> None:
        """Schedule templates must come from YAML, not inline Python dicts."""
        import dnd_simulator.layers.entities.models as models_mod

        source = inspect.getsource(models_mod)
        assert "DEFAULT_SCHEDULE_TEMPLATES" not in source
        assert "ACTIVITY_FLAVOR" not in source


class TestScheduleFromYaml:
    def test_blacksmith_schedule_resolves_correctly(self) -> None:
        """Blacksmith schedule loaded from YAML resolves to settlement-prefixed locations."""
        entries = resolve_schedule(NpcRole.BLACKSMITH, "town")
        assert len(entries) == 3
        activities = [(e.start_hour, e.end_hour, e.activity, e.location_id) for e in entries]
        assert (21, 7, NpcActivity.SLEEPING, "town_home") in activities
        assert (7, 19, NpcActivity.WORKING, "town_smithy") in activities
        assert (19, 21, NpcActivity.IDLE, "town_tavern") in activities

    def test_guard_schedule_has_two_entries(self) -> None:
        entries = resolve_schedule(NpcRole.GUARD, "city")
        assert len(entries) == 2
        assert entries[0].activity == NpcActivity.SLEEPING
        assert entries[1].activity == NpcActivity.WORKING

    def test_merchant_schedule_has_three_entries(self) -> None:
        entries = resolve_schedule(NpcRole.MERCHANT, "city")
        assert len(entries) == 3

    def test_commoner_has_no_schedule(self) -> None:
        entries = resolve_schedule(NpcRole.COMMONER, "city")
        assert entries == []


class TestActivityFlavorFromYaml:
    def test_guard_working_flavor(self) -> None:
        assert activity_flavor(NpcRole.GUARD, NpcActivity.WORKING) == "standing watch"

    def test_blacksmith_working_flavor(self) -> None:
        assert activity_flavor(NpcRole.BLACKSMITH, NpcActivity.WORKING) == "hammering at the anvil"

    def test_merchant_idle_flavor(self) -> None:
        assert activity_flavor(NpcRole.MERCHANT, NpcActivity.IDLE) == "counting coins at a table"

    def test_unknown_role_falls_back_to_generic(self) -> None:
        result = activity_flavor(NpcRole.COMMONER, NpcActivity.WORKING)
        assert result == "busy at work"


class TestDialogueStillWorks:
    """Dialogue stays in Python for i18n — verify it still functions."""

    def test_merchant_working_dialogue(self) -> None:
        line = canned_line(NpcRole.MERCHANT, NpcActivity.WORKING, [])
        assert "buy" in line.lower()

    def test_mood_override_takes_priority(self) -> None:
        line = canned_line(NpcRole.MERCHANT, NpcActivity.WORKING, ["angry"])
        assert line == "Leave me alone!"

    def test_generic_fallback_for_sleeping(self) -> None:
        line = canned_line(NpcRole.GUARD, NpcActivity.SLEEPING, [])
        assert line == "Zzz..."
