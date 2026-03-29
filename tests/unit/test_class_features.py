"""Tests for class features composition system."""

from __future__ import annotations

import pytest

from dnd_simulator.content_loader import parse_class_features
from dnd_simulator.core.character import Character, CharClass
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle, RogueFeatures

# ---------------------------------------------------------------------------
# Character.get_feature
# ---------------------------------------------------------------------------


class TestGetFeature:
    def test_get_existing_feature(self) -> None:
        char = Character(
            id="f1",
            name="Fighter",
            location_id="arena",
            char_class=CharClass.FIGHTER,
            class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        )
        feat = char.get_feature(FighterFeatures)
        assert feat is not None
        assert feat.fighting_style == FightingStyle.DEFENSE

    def test_get_missing_feature_returns_none(self) -> None:
        char = Character(
            id="f1",
            name="Fighter",
            location_id="arena",
            char_class=CharClass.FIGHTER,
            class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        )
        assert char.get_feature(RogueFeatures) is None

    def test_empty_features(self) -> None:
        char = Character(id="c1", name="Commoner", location_id="arena")
        assert char.get_feature(FighterFeatures) is None
        assert char.get_feature(RogueFeatures) is None

    def test_multiclass_both_features(self) -> None:
        char = Character(
            id="mc1",
            name="Multiclass",
            location_id="arena",
            class_features=[
                FighterFeatures(fighting_style=FightingStyle.DUELING),
                RogueFeatures(sneak_attack_dice=2),
            ],
        )
        fighter = char.get_feature(FighterFeatures)
        rogue = char.get_feature(RogueFeatures)
        assert fighter is not None
        assert fighter.fighting_style == FightingStyle.DUELING
        assert rogue is not None
        assert rogue.sneak_attack_dice == 2


# ---------------------------------------------------------------------------
# parse_class_features
# ---------------------------------------------------------------------------


class TestParseClassFeatures:
    def test_fighter_with_style(self) -> None:
        features = parse_class_features(
            CharClass.FIGHTER,
            {"class_features": {"fighting_style": "defense"}},
        )
        assert len(features) == 1
        assert isinstance(features[0], FighterFeatures)
        assert features[0].fighting_style == FightingStyle.DEFENSE

    def test_fighter_dueling(self) -> None:
        features = parse_class_features(
            CharClass.FIGHTER,
            {"class_features": {"fighting_style": "dueling"}},
        )
        assert features[0].fighting_style == FightingStyle.DUELING

    def test_fighter_no_features_block(self) -> None:
        features = parse_class_features(CharClass.FIGHTER, {})
        assert features == []

    def test_rogue_auto_features(self) -> None:
        features = parse_class_features(CharClass.ROGUE, {})
        assert len(features) == 1
        assert isinstance(features[0], RogueFeatures)
        assert features[0].sneak_attack_dice == 1

    def test_rogue_custom_sneak_dice(self) -> None:
        features = parse_class_features(
            CharClass.ROGUE,
            {"class_features": {"sneak_attack_dice": 3}},
        )
        assert features[0].sneak_attack_dice == 3

    def test_fighter_class_features_block_without_style_raises(self) -> None:
        with pytest.raises(ValueError, match="fighting_style"):
            parse_class_features(CharClass.FIGHTER, {"class_features": {"some_other_key": True}})

    def test_commoner_no_features(self) -> None:
        features = parse_class_features(CharClass.COMMONER, {})
        assert features == []

    def test_wizard_no_features(self) -> None:
        features = parse_class_features(CharClass.WIZARD, {})
        assert features == []
