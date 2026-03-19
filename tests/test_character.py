"""Tests for entity hierarchy, ability scores, and perception."""

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Alignment,
    Character,
    CharClass,
    Entity,
    Race,
)
from dnd_simulator.core.player import PlayerCharacter


class TestAbilityScores:
    def test_defaults_all_ten(self) -> None:
        scores = AbilityScores()
        for ability in Ability:
            assert scores[ability] == 10

    def test_modifier_10_is_zero(self) -> None:
        scores = AbilityScores()
        assert scores.modifier(Ability.STR) == 0

    def test_modifier_16_is_plus_3(self) -> None:
        scores = AbilityScores()
        scores[Ability.STR] = 16
        assert scores.modifier(Ability.STR) == 3

    def test_modifier_8_is_minus_1(self) -> None:
        scores = AbilityScores()
        scores[Ability.CHA] = 8
        assert scores.modifier(Ability.CHA) == -1

    def test_modifier_odd_rounds_down(self) -> None:
        scores = AbilityScores()
        scores[Ability.DEX] = 15
        assert scores.modifier(Ability.DEX) == 2

    def test_round_trip_dict(self) -> None:
        scores = AbilityScores()
        scores[Ability.STR] = 18
        scores[Ability.WIS] = 14
        d = scores.to_dict()
        restored = AbilityScores.from_dict(d)
        assert restored[Ability.STR] == 18
        assert restored[Ability.WIS] == 14
        assert restored[Ability.DEX] == 10


class TestEntityHierarchy:
    def test_entity_fields(self) -> None:
        e = Entity(id="e1", name="Rock", region_id="r1")
        assert e.id == "e1"
        assert e.name == "Rock"

    def test_character_defaults(self) -> None:
        c = Character(id="c1", name="John", region_id="r1")
        assert c.race == Race.HUMAN
        assert c.char_class == CharClass.COMMONER
        assert c.level == 1
        assert c.alignment == Alignment.TRUE_NEUTRAL
        assert c.max_hp == 4
        assert c.gold == 0

    def test_character_custom_fields(self) -> None:
        c = Character(
            id="c2",
            name="Kael",
            region_id="r1",
            race=Race.TIEFLING,
            char_class=CharClass.FIGHTER,
            level=3,
            alignment=Alignment.CHAOTIC_GOOD,
            max_hp=28,
            current_hp=28,
            gold=100,
        )
        assert c.race == Race.TIEFLING
        assert c.char_class == CharClass.FIGHTER
        assert c.level == 3

    def test_player_character_extends_character(self) -> None:
        p = PlayerCharacter(
            id="player",
            name="Hero",
            region_id="r1",
            race=Race.ELF,
            char_class=CharClass.WIZARD,
        )
        assert isinstance(p, Character)
        assert isinstance(p, Entity)


class TestPerceive:
    def test_perceive_character_sees_race(self) -> None:
        observer = Character(id="obs", name="Observer", region_id="r1")
        target = Character(
            id="tgt",
            name="Target",
            region_id="r1",
            race=Race.TIEFLING,
        )
        result = observer.perceive(target)
        assert "tiefling" in result

    def test_perceive_includes_appearance(self) -> None:
        observer = Character(id="obs", name="Observer", region_id="r1")
        target = Character(
            id="tgt",
            name="Target",
            region_id="r1",
            race=Race.DWARF,
            appearance="short with a braided red beard",
        )
        result = observer.perceive(target)
        assert "dwarf" in result
        assert "braided red beard" in result

    def test_perceive_wounded(self) -> None:
        observer = Character(id="obs", name="Observer", region_id="r1")
        target = Character(
            id="tgt",
            name="Target",
            region_id="r1",
            max_hp=20,
            current_hp=5,
        )
        result = observer.perceive(target)
        assert "ранен" in result

    def test_perceive_healthy_no_wound(self) -> None:
        observer = Character(id="obs", name="Observer", region_id="r1")
        target = Character(
            id="tgt",
            name="Target",
            region_id="r1",
            max_hp=20,
            current_hp=20,
        )
        result = observer.perceive(target)
        assert "ранен" not in result

    def test_perceive_entity_returns_name(self) -> None:
        observer = Character(id="obs", name="Observer", region_id="r1")
        target = Entity(id="wolf", name="Grey Wolf", region_id="r1")
        result = observer.perceive(target)
        assert result == "Grey Wolf"

    def test_perceive_half_orc_label(self) -> None:
        observer = Character(id="obs", name="Observer", region_id="r1")
        target = Character(id="tgt", name="Grok", region_id="r1", race=Race.HALF_ORC)
        result = observer.perceive(target)
        assert "half orc" in result


class TestPlayerSaveLoad:
    def test_save_data(self) -> None:
        p = PlayerCharacter(
            id="player",
            name="Hero",
            region_id="r1",
            current_hp=8,
            max_hp=12,
            gold=50,
        )
        data = p.to_save_data()
        assert data["region_id"] == "r1"
        assert data["current_hp"] == 8
        assert data["gold"] == 50

    def test_load_save_data(self) -> None:
        p = PlayerCharacter(
            id="player",
            name="Hero",
            region_id="r1",
            current_hp=12,
            max_hp=12,
            gold=50,
        )
        p.load_save_data({"region_id": "r2", "current_hp": 3, "gold": 10})
        assert p.region_id == "r2"
        assert p.current_hp == 3
        assert p.gold == 10

    def test_load_partial_data(self) -> None:
        p = PlayerCharacter(
            id="player",
            name="Hero",
            region_id="r1",
            current_hp=12,
            max_hp=12,
            gold=50,
        )
        p.load_save_data({"region_id": "r2"})
        assert p.region_id == "r2"
        assert p.current_hp == 12  # unchanged
        assert p.gold == 50  # unchanged
