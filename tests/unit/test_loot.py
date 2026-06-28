"""Tests for the derived lootable state (`rules/loot.py`)."""

from __future__ import annotations

from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.rules.loot import is_lootable


class TestIsLootable:
    def test_living_creature_is_not_lootable(self) -> None:
        pc = PlayerCharacter(id="p", name="Aldric", location_id="loc", max_hp=10, current_hp=10)
        assert is_lootable(pc) is False

    def test_dead_creature_is_lootable(self) -> None:
        pc = PlayerCharacter(id="p", name="Aldric", location_id="loc", max_hp=10, current_hp=10)
        pc.take_damage(10)
        assert pc.is_alive is False
        assert is_lootable(pc) is True
