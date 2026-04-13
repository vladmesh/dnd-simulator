"""Unit tests for ``rules/perform_level_up.py`` (sprint 017 phase 5 task 3).

Covers each supported class transition (L1→L2) and the validation paths
(missing style, inapplicable style, no level-up available, resource pool merge).
"""

from __future__ import annotations

import pytest

from dnd_simulator.core.character import (
    AbilityScores,
    Character,
    CharClass,
    Race,
)
from dnd_simulator.core.class_features import (
    FighterFeatures,
    FightingStyle,
    PaladinFeatures,
    RogueFeatures,
)
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.rules.perform_level_up import perform_level_up


def _fighter_l1() -> Character:
    return Character(
        id="f",
        name="F",
        location_id="loc",
        max_hp=10,
        current_hp=10,
        ac=10,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=1,
        ability_scores=AbilityScores(),
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE, level=1)],
        resource_pools=[ResourcePool(id="second_wind", max_uses=1, current_uses=1, reset_on=RestType.SHORT_REST)],
        level_up_available=True,
    )


def _rogue_l1() -> Character:
    return Character(
        id="r",
        name="R",
        location_id="loc",
        max_hp=8,
        current_hp=8,
        ac=10,
        race=Race.HUMAN,
        char_class=CharClass.ROGUE,
        level=1,
        ability_scores=AbilityScores(),
        class_features=[RogueFeatures(level=1)],
        resource_pools=[],
        level_up_available=True,
    )


def _paladin_l1() -> Character:
    return Character(
        id="p",
        name="P",
        location_id="loc",
        max_hp=10,
        current_hp=10,
        ac=10,
        race=Race.HUMAN,
        char_class=CharClass.PALADIN,
        level=1,
        ability_scores=AbilityScores(),
        class_features=[PaladinFeatures(level=1)],
        resource_pools=[
            ResourcePool(id="lay_on_hands", max_uses=5, current_uses=5, reset_on=RestType.LONG_REST),
        ],
        level_up_available=True,
    )


def _pool(character: Character, pool_id: str) -> ResourcePool | None:
    return next((p for p in character.resource_pools if p.id == pool_id), None)


class TestFighterLevelUp:
    def test_l1_to_l2_no_style(self) -> None:
        c = _fighter_l1()
        perform_level_up(c, fighting_style=None)
        assert c.level == 2
        assert c.level_up_available is False
        # d10, CON mod 0: L1=10, L2=10+6=16, delta=6
        assert c.max_hp == 16
        assert c.current_hp == 16
        assert len(c.class_features) == 1
        feat = c.class_features[0]
        assert isinstance(feat, FighterFeatures)
        assert feat.level == 2
        assert feat.fighting_style == FightingStyle.DEFENSE
        surge = _pool(c, "action_surge")
        assert surge is not None
        assert surge.max_uses == 1
        assert surge.current_uses == 1

    def test_l1_to_l2_hp_delta_applies_to_current(self) -> None:
        c = _fighter_l1()
        c.current_hp = 5  # wounded
        perform_level_up(c, fighting_style=None)
        # delta=6, current goes 5 → 11
        assert c.current_hp == 11
        assert c.max_hp == 16

    def test_style_passed_raises(self) -> None:
        c = _fighter_l1()
        with pytest.raises(ValueError, match="fighting_style is not applicable"):
            perform_level_up(c, fighting_style=FightingStyle.DUELING)


class TestRogueLevelUp:
    def test_l1_to_l2_no_style(self) -> None:
        c = _rogue_l1()
        perform_level_up(c, fighting_style=None)
        assert c.level == 2
        assert c.level_up_available is False
        # d8, CON mod 0: L1=8, L2=8+5=13, delta=5
        assert c.max_hp == 13
        assert c.current_hp == 13
        assert len(c.class_features) == 1
        feat = c.class_features[0]
        assert isinstance(feat, RogueFeatures)
        assert feat.level == 2
        assert c.resource_pools == []


class TestPaladinLevelUp:
    def test_l1_to_l2_defense(self) -> None:
        c = _paladin_l1()
        perform_level_up(c, fighting_style=FightingStyle.DEFENSE)
        assert c.level == 2
        feat = c.class_features[0]
        assert isinstance(feat, PaladinFeatures)
        assert feat.level == 2
        assert feat.fighting_style == FightingStyle.DEFENSE
        slot = _pool(c, "spell_slot_1")
        assert slot is not None
        assert slot.max_uses == 2
        assert slot.current_uses == 2

    def test_l1_to_l2_dueling(self) -> None:
        c = _paladin_l1()
        perform_level_up(c, fighting_style=FightingStyle.DUELING)
        feat = c.class_features[0]
        assert isinstance(feat, PaladinFeatures)
        assert feat.fighting_style == FightingStyle.DUELING

    def test_l1_to_l2_missing_style_raises(self) -> None:
        c = _paladin_l1()
        with pytest.raises(ValueError, match="Paladin level 2 requires a fighting_style"):
            perform_level_up(c, fighting_style=None)


class TestNoLevelUpAvailable:
    def test_raises_when_flag_false(self) -> None:
        c = _fighter_l1()
        c.level_up_available = False
        with pytest.raises(ValueError, match="No level-up available"):
            perform_level_up(c, fighting_style=None)


class TestResourcePoolMerge:
    def test_paladin_loh_current_uses_preserved(self) -> None:
        c = _paladin_l1()
        # Partially-used LoH pool: 2/5 remaining before level up
        loh_before = _pool(c, "lay_on_hands")
        assert loh_before is not None
        loh_before.current_uses = 2
        perform_level_up(c, fighting_style=FightingStyle.DEFENSE)
        loh_after = _pool(c, "lay_on_hands")
        assert loh_after is not None
        # Max grows to 5 * level = 10; current_uses preserved at 2
        assert loh_after.max_uses == 10
        assert loh_after.current_uses == 2
