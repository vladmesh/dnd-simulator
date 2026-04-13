"""Tests for level-aware class features (sprint 017 phase 2 task 1).

Paladin FS and Divine Smite gated at L2 (PHB-correct). Fighter FS stays L1.
Rogue features carry a level field (no behavior change yet).
"""

from __future__ import annotations

from dnd_simulator.content_loader.creatures import parse_class_features
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Character,
    CharClass,
    Creature,
    Race,
)
from dnd_simulator.core.class_features import (
    FighterFeatures,
    FightingStyle,
    PaladinFeatures,
    RogueFeatures,
)
from dnd_simulator.core.items import Item, ItemType, WeaponCategory, WeaponDef
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.rules.divine_smite import validate_smite
from dnd_simulator.rules.modifiers import attack_modifiers
from dnd_simulator.rules.resources import spell_slot_pool_id

_LONGSWORD = WeaponDef(
    weapon_id="longsword",
    attack_name="longsword slash",
    category=WeaponCategory.MARTIAL,
    damage=(),
    ability=Ability.STR,
)


def _scores(strength: int = 16) -> AbilityScores:
    base = AbilityScores().scores
    return AbilityScores(scores={**base, Ability.STR: strength})


def _paladin(*, level: int, fighting_style: FightingStyle | None = FightingStyle.DUELING) -> Character:
    weapon = Item(id="ls", name="Longsword", item_type=ItemType.WEAPON, weapon_def=_LONGSWORD)
    return Character(
        id="pal",
        name="Pal",
        location_id="loc",
        max_hp=20,
        current_hp=20,
        ac=10,
        race=Race.HUMAN,
        char_class=CharClass.PALADIN,
        level=level,
        ability_scores=_scores(),
        class_features=[PaladinFeatures(fighting_style=fighting_style, level=level)],
        equipped_weapon=weapon,
    )


def _target() -> Creature:
    return Creature(id="t", name="T", location_id="loc", max_hp=10, current_hp=10, ac=5)


class TestPaladinLevelGatedFightingStyle:
    def test_l1_paladin_gets_no_dueling_bonus(self) -> None:
        paladin = _paladin(level=1, fighting_style=FightingStyle.DUELING)
        result = attack_modifiers(paladin, _target(), melee=True)
        # STR 16 → +3 only, no Dueling +2
        assert result.damage_bonus == 3

    def test_l2_paladin_gets_dueling_bonus(self) -> None:
        paladin = _paladin(level=2, fighting_style=FightingStyle.DUELING)
        result = attack_modifiers(paladin, _target(), melee=True)
        assert result.damage_bonus == 5  # STR +3, Dueling +2


class TestValidateSmiteLevelGate:
    def test_l1_paladin_cannot_smite(self) -> None:
        paladin = Character(
            id="p1",
            name="P1",
            location_id="loc",
            max_hp=12,
            current_hp=12,
            ac=16,
            race=Race.HUMAN,
            char_class=CharClass.PALADIN,
            level=1,
            class_features=[PaladinFeatures(level=1)],
            resource_pools=[
                ResourcePool(spell_slot_pool_id(1), 1, 1, RestType.LONG_REST),
            ],
        )
        error = validate_smite(paladin, slot_level=1)
        assert error is not None
        assert "level 2" in error.lower()

    def test_l2_paladin_with_slot_can_smite(self) -> None:
        paladin = Character(
            id="p2",
            name="P2",
            location_id="loc",
            max_hp=18,
            current_hp=18,
            ac=16,
            race=Race.HUMAN,
            char_class=CharClass.PALADIN,
            level=2,
            class_features=[PaladinFeatures(level=2)],
            resource_pools=[
                ResourcePool(spell_slot_pool_id(1), 2, 2, RestType.LONG_REST),
            ],
        )
        assert validate_smite(paladin, slot_level=1) is None


class TestFighterL1FightingStyleStillWorks:
    def test_fighter_l1_defense_gives_ac(self) -> None:
        from dnd_simulator.core.items import ArmorCategory, ArmorDef
        from dnd_simulator.rules.modifiers import effective_ac

        chain_mail = ArmorDef(armor_id="chain_mail", base_ac=16, max_dex_bonus=0, category=ArmorCategory.HEAVY)
        fighter = Character(
            id="f1",
            name="F1",
            location_id="loc",
            max_hp=12,
            current_hp=12,
            ac=10,
            race=Race.HUMAN,
            char_class=CharClass.FIGHTER,
            level=1,
            class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE, level=1)],
        )
        fighter.equipped_armor = Item(id="cm", name="Chain Mail", item_type=ItemType.ARMOR, armor_def=chain_mail)
        assert effective_ac(fighter) == 17  # 16 armor + 1 Defense

    def test_parse_class_features_fighter_has_level_1(self) -> None:
        feats = parse_class_features(CharClass.FIGHTER, {"class_features": {"fighting_style": "defense"}})
        assert len(feats) == 1
        assert isinstance(feats[0], FighterFeatures)
        assert feats[0].level == 1
        assert feats[0].fighting_style == FightingStyle.DEFENSE


class TestRogueFeaturesCarryLevel:
    def test_parse_rogue_default_level_1(self) -> None:
        feats = parse_class_features(CharClass.ROGUE, {})
        assert len(feats) == 1
        assert isinstance(feats[0], RogueFeatures)
        assert feats[0].level == 1
        # Cunning Action overrides still present
        assert feats[0].cost_overrides  # non-empty


class TestContentLoaderPassesLevel:
    def test_paladin_npc_features_level_matches_character_level(self) -> None:
        from dnd_simulator.content_loader.creatures import parse_npc

        npc_data = {
            "name": {"en": "Sir Ector"},
            "start_location": "temple",
            "faction": "kingdom",
            "role": "guard",
            "ai": "rule_based",
            "class": "paladin",
            "level": 2,
            "hp": 18,
            "ac": 16,
            "ability_scores": {"str": 16, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 14},
            "class_features": {"fighting_style": "defense"},
            "items": [],
        }
        npc = parse_npc("ector", npc_data, lang="en")
        feat = npc.get_feature(PaladinFeatures)
        assert feat is not None
        assert feat.level == 2
