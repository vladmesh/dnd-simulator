"""Tests for Paladin class infrastructure — Phase 2, Task 1.

Covers: PaladinFeatures, resource pools (Lay on Hands + spell slots),
variable resource spending, content loader, starting equipment, HP.
"""

from __future__ import annotations

import pytest

from dnd_simulator.content_loader.creatures import (
    build_class_resource_pools,
    parse_class_features,
    parse_npc,
)
from dnd_simulator.core.character import Character, CharClass
from dnd_simulator.core.class_features import (
    FighterFeatures,
    FightingStyle,
    PaladinFeatures,
)
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.rules.character_creation import HIT_DICE, calculate_max_hp, starting_equipment
from dnd_simulator.rules.resources import use_resource

# ---------------------------------------------------------------------------
# PaladinFeatures dataclass
# ---------------------------------------------------------------------------


class TestPaladinFeatures:
    def test_create_with_fighting_style(self) -> None:
        feat = PaladinFeatures(fighting_style=FightingStyle.DEFENSE)
        assert feat.fighting_style == FightingStyle.DEFENSE

    def test_frozen(self) -> None:
        feat = PaladinFeatures(fighting_style=FightingStyle.DUELING)
        with pytest.raises(AttributeError):
            feat.fighting_style = FightingStyle.DEFENSE  # type: ignore[misc]

    def test_is_valid_class_features(self) -> None:
        """PaladinFeatures should be retrievable via Character.get_feature."""
        char = Character(
            id="p1",
            name="Paladin",
            location_id="temple",
            char_class=CharClass.PALADIN,
            class_features=[PaladinFeatures(fighting_style=FightingStyle.DEFENSE)],
        )
        feat = char.get_feature(PaladinFeatures)
        assert feat is not None
        assert feat.fighting_style == FightingStyle.DEFENSE

    def test_get_feature_returns_none_for_other_class(self) -> None:
        char = Character(
            id="f1",
            name="Fighter",
            location_id="arena",
            char_class=CharClass.FIGHTER,
            class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        )
        assert char.get_feature(PaladinFeatures) is None


# ---------------------------------------------------------------------------
# build_class_resource_pools — Paladin
# ---------------------------------------------------------------------------


class TestPaladinResourcePools:
    def test_level1_lay_on_hands_pool(self) -> None:
        """Paladin level 1: Lay on Hands pool = 5 * 1 = 5."""
        pools = build_class_resource_pools(CharClass.PALADIN, level=1)
        loh = next(p for p in pools if p.id == "lay_on_hands")
        assert loh.max_uses == 5
        assert loh.current_uses == 5
        assert loh.reset_on == RestType.LONG_REST

    def test_level3_lay_on_hands_pool(self) -> None:
        """Paladin level 3: Lay on Hands pool = 5 * 3 = 15."""
        pools = build_class_resource_pools(CharClass.PALADIN, level=3)
        loh = next(p for p in pools if p.id == "lay_on_hands")
        assert loh.max_uses == 15

    def test_level1_one_spell_slot(self) -> None:
        """Paladin level 1: 1 first-level spell slot (temporary until leveling exists)."""
        pools = build_class_resource_pools(CharClass.PALADIN, level=1)
        slot1 = next(p for p in pools if p.id == "spell_slot_1")
        assert slot1.max_uses == 1
        assert slot1.current_uses == 1
        assert slot1.reset_on == RestType.LONG_REST

    def test_level2_spell_slots(self) -> None:
        """Paladin level 2: 2 first-level spell slots."""
        pools = build_class_resource_pools(CharClass.PALADIN, level=2)
        slot1 = next(p for p in pools if p.id == "spell_slot_1")
        assert slot1.max_uses == 2
        assert slot1.current_uses == 2
        assert slot1.reset_on == RestType.LONG_REST

    def test_backward_compat_fighter_no_level(self) -> None:
        """Fighter still works without explicit level parameter."""
        pools = build_class_resource_pools(CharClass.FIGHTER)
        sw = next(p for p in pools if p.id == "second_wind")
        assert sw.max_uses == 1
        assert sw.reset_on == RestType.SHORT_REST


# ---------------------------------------------------------------------------
# Variable resource spending (use_resource with amount)
# ---------------------------------------------------------------------------


def _creature_with_pool(pool: ResourcePool) -> Character:
    c = Character(id="test", name="Test", location_id="arena", max_hp=30, current_hp=30, ac=10)
    c.resource_pools = [pool]
    return c


class TestVariableResourceSpending:
    def test_spend_partial_amount(self) -> None:
        pool = ResourcePool("lay_on_hands", 25, 25, RestType.LONG_REST)
        creature = _creature_with_pool(pool)
        use_resource(creature, "lay_on_hands", amount=10)
        assert pool.current_uses == 15

    def test_spend_full_amount(self) -> None:
        pool = ResourcePool("lay_on_hands", 25, 25, RestType.LONG_REST)
        creature = _creature_with_pool(pool)
        use_resource(creature, "lay_on_hands", amount=25)
        assert pool.current_uses == 0

    def test_spend_more_than_remaining_raises(self) -> None:
        pool = ResourcePool("lay_on_hands", 25, 3, RestType.LONG_REST)
        creature = _creature_with_pool(pool)
        with pytest.raises(ValueError, match=r"exhausted|insufficient"):
            use_resource(creature, "lay_on_hands", amount=5)

    def test_default_amount_is_1(self) -> None:
        """Existing behavior: use_resource without amount spends 1."""
        pool = ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)
        creature = _creature_with_pool(pool)
        use_resource(creature, "second_wind")
        assert pool.current_uses == 0

    def test_amount_zero_raises(self) -> None:
        pool = ResourcePool("lay_on_hands", 25, 25, RestType.LONG_REST)
        creature = _creature_with_pool(pool)
        with pytest.raises(ValueError, match="amount must be >= 1"):
            use_resource(creature, "lay_on_hands", amount=0)


# ---------------------------------------------------------------------------
# parse_class_features — Paladin
# ---------------------------------------------------------------------------


class TestParseClassFeaturesPaladin:
    def test_paladin_with_fighting_style(self) -> None:
        features = parse_class_features(
            CharClass.PALADIN,
            {"class_features": {"fighting_style": "defense"}},
        )
        assert len(features) == 1
        assert isinstance(features[0], PaladinFeatures)
        assert features[0].fighting_style == FightingStyle.DEFENSE

    def test_paladin_no_features_block(self) -> None:
        """Paladin without class_features block gets PaladinFeatures with no style."""
        features = parse_class_features(CharClass.PALADIN, {})
        assert len(features) == 1
        assert isinstance(features[0], PaladinFeatures)
        assert features[0].fighting_style is None


# ---------------------------------------------------------------------------
# Content loader — full NPC parsing
# ---------------------------------------------------------------------------


class TestPaladinNpcParsing:
    def test_parse_paladin_npc(self) -> None:
        """A Paladin NPC should have PaladinFeatures and correct resource pools."""
        npc_data = {
            "name": {"en": "Brother Aldwyn"},
            "start_location": "temple",
            "faction": "kingdom",
            "role": "guard",
            "ai": "rule",
            "class": "paladin",
            "level": 2,
            "hp": 18,
            "ac": 16,
            "ability_scores": {"str": 16, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 14},
            "class_features": {"fighting_style": "defense"},
            "items": [],
        }
        npc = parse_npc("aldwyn", npc_data, lang="en")
        assert npc.char_class == CharClass.PALADIN

        # Class features
        feat = npc.get_feature(PaladinFeatures)
        assert feat is not None
        assert feat.fighting_style == FightingStyle.DEFENSE

        # Resource pools: lay_on_hands (5 * 2 = 10) + spell_slot_1 (2)
        pool_ids = {p.id for p in npc.resource_pools}
        assert "lay_on_hands" in pool_ids
        assert "spell_slot_1" in pool_ids

        loh = next(p for p in npc.resource_pools if p.id == "lay_on_hands")
        assert loh.max_uses == 10  # 5 * level 2

        slot = next(p for p in npc.resource_pools if p.id == "spell_slot_1")
        assert slot.max_uses == 2


# ---------------------------------------------------------------------------
# Character creation — HP and equipment
# ---------------------------------------------------------------------------


class TestPaladinCharacterCreation:
    def test_hit_die_d10(self) -> None:
        assert HIT_DICE[CharClass.PALADIN] == 10

    def test_hp_level1_con14(self) -> None:
        # d10 + 2 = 12
        assert calculate_max_hp(CharClass.PALADIN, level=1, con_modifier=2) == 12

    def test_hp_level3_con14(self) -> None:
        # L1: 10+2=12, L2-3: 2*(6+2)=16, total=28
        assert calculate_max_hp(CharClass.PALADIN, level=3, con_modifier=2) == 28

    def test_starting_equipment(self) -> None:
        equip = starting_equipment(CharClass.PALADIN)
        assert set(equip) == {"chain_mail", "longsword", "shield"}

    def test_starting_equipment_returns_copy(self) -> None:
        a = starting_equipment(CharClass.PALADIN)
        b = starting_equipment(CharClass.PALADIN)
        assert a is not b
