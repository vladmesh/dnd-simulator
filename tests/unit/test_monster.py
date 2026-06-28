"""Tests for MonsterTemplate + EncounterTable models and YAML loading."""

from pathlib import Path

import pytest
import yaml

from dnd_simulator.core.character import Ability, AbilityScores, DamageType
from dnd_simulator.core.monster import EncounterEntry, MonsterTemplate


class TestMonsterTemplate:
    """MonsterTemplate frozen dataclass with D&D-relevant fields."""

    def test_template_has_all_combat_fields(self) -> None:
        from dnd_simulator.core.character import Attack, DamageComponent

        template = MonsterTemplate(
            id="goblin",
            name="Goblin",
            hp=7,
            ac=15,
            speed=30,
            ability_scores=AbilityScores.from_dict({"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8}),
            attacks=(
                Attack(
                    name="scimitar",
                    ability=Ability.DEX,
                    damage=(DamageComponent(dice="1d6", type=DamageType.SLASHING),),
                    reach=5,
                ),
            ),
            cr=0.25,
        )
        assert template.id == "goblin"
        assert template.hp == 7
        assert template.ac == 15
        assert template.speed == 30
        assert template.cr == 0.25
        assert len(template.attacks) == 1
        assert template.attacks[0].name == "scimitar"

    def test_template_is_frozen(self) -> None:
        template = MonsterTemplate(
            id="wolf",
            name="Wolf",
            hp=11,
            ac=13,
            speed=40,
            ability_scores=AbilityScores(),
            attacks=(),
            cr=0.25,
        )
        with pytest.raises(AttributeError):
            template.hp = 99  # type: ignore[misc]


class TestEncounterEntry:
    """EncounterEntry maps a template to spawn chance and count range."""

    def test_entry_fields(self) -> None:
        entry = EncounterEntry(
            template_id="goblin",
            chance=0.3,
            count_min=1,
            count_max=3,
        )
        assert entry.template_id == "goblin"
        assert entry.chance == 0.3
        assert entry.count_min == 1
        assert entry.count_max == 3

    def test_entry_is_frozen(self) -> None:
        entry = EncounterEntry(template_id="goblin", chance=0.3, count_min=1, count_max=3)
        with pytest.raises(AttributeError):
            entry.chance = 0.5  # type: ignore[misc]


class TestParseMonsterTemplate:
    """parse_monster_template produces valid MonsterTemplate from YAML data."""

    def test_parse_full_template(self) -> None:
        from dnd_simulator.content_loader import parse_monster_template

        data = {
            "name": {"en": "Goblin", "ru": "Гоблин"},
            "hp": 7,
            "ac": 15,
            "speed": 30,
            "ability_scores": {"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
            "attacks": [
                {
                    "name": "scimitar",
                    "ability": "dex",
                    "damage": [{"dice": "1d6", "type": "slashing"}],
                    "reach": 5,
                }
            ],
            "cr": 0.25,
        }

        template = parse_monster_template("goblin", data, lang="en")

        assert template.id == "goblin"
        assert template.name == "Goblin"
        assert template.hp == 7
        assert template.ac == 15
        assert template.speed == 30
        assert template.ability_scores[Ability.DEX] == 14
        assert template.ability_scores[Ability.STR] == 8
        assert template.cr == 0.25

    def test_parse_template_attacks_are_attack_objects(self) -> None:
        """Attacks parsed from YAML should be core.character.Attack instances."""
        from dnd_simulator.content_loader import parse_monster_template

        data = {
            "name": "Wolf",
            "hp": 11,
            "ac": 13,
            "speed": 40,
            "ability_scores": {"str": 12, "dex": 15, "con": 12, "int": 3, "wis": 12, "cha": 6},
            "attacks": [
                {
                    "name": "bite",
                    "ability": "dex",
                    "damage": [{"dice": "2d4", "type": "piercing"}],
                    "reach": 5,
                }
            ],
            "cr": 0.25,
        }

        template = parse_monster_template("wolf", data, lang="en")

        assert len(template.attacks) == 1
        attack = template.attacks[0]
        # Attack is the core.character.Attack frozen dataclass
        from dnd_simulator.core.character import Attack

        assert isinstance(attack, Attack)
        assert attack.name == "bite"
        assert attack.ability == Ability.DEX
        assert attack.damage[0].dice == "2d4"
        assert attack.damage[0].type == DamageType.PIERCING
        assert attack.reach == 5

    def test_parse_template_i18n_name(self) -> None:
        from dnd_simulator.content_loader import parse_monster_template

        data = {
            "name": {"en": "Goblin", "ru": "Гоблин"},
            "hp": 7,
            "ac": 15,
            "speed": 30,
            "attacks": [],
            "cr": 0.25,
        }
        template_en = parse_monster_template("goblin", data, lang="en")
        template_ru = parse_monster_template("goblin", data, lang="ru")
        assert template_en.name == "Goblin"
        assert template_ru.name == "Гоблин"

    def test_parse_template_default_ability_scores(self) -> None:
        """Missing ability_scores → all 10s."""
        from dnd_simulator.content_loader import parse_monster_template

        data = {"name": "Blob", "hp": 5, "ac": 8, "speed": 10, "attacks": [], "cr": 0.0}
        template = parse_monster_template("blob", data, lang="en")
        assert template.ability_scores[Ability.STR] == 10
        assert template.ability_scores[Ability.DEX] == 10


class TestParseEncounters:
    """parse_encounters produces location_id → list[EncounterEntry] mapping."""

    def test_parse_encounter_table(self) -> None:
        from dnd_simulator.content_loader import parse_encounters

        data = {
            "dark_forest_path": [
                {"template": "goblin", "chance": 0.3, "count": [1, 3]},
                {"template": "wolf", "chance": 0.1, "count": [2, 4]},
            ]
        }
        known_templates = {"goblin", "wolf"}
        encounters = parse_encounters(data, known_templates)

        assert "dark_forest_path" in encounters
        entries = encounters["dark_forest_path"]
        assert len(entries) == 2

        assert entries[0].template_id == "goblin"
        assert entries[0].chance == 0.3
        assert entries[0].count_min == 1
        assert entries[0].count_max == 3

        assert entries[1].template_id == "wolf"
        assert entries[1].chance == 0.1
        assert entries[1].count_min == 2
        assert entries[1].count_max == 4

    def test_parse_encounter_unknown_template_raises(self) -> None:
        from dnd_simulator.content_loader import parse_encounters

        data = {"forest": [{"template": "dragon", "chance": 0.5, "count": [1, 1]}]}
        with pytest.raises(RuntimeError, match="dragon"):
            parse_encounters(data, known_templates={"goblin"})


class TestParseRegionEncounters:
    """parse_region_encounters keys by region_id and fails fast on bad refs."""

    def test_parse_region_encounter_table(self) -> None:
        from dnd_simulator.content_loader import parse_region_encounters

        data = {"darkwood": [{"template": "goblin", "chance": 0.4, "count": [1, 3]}]}
        encounters = parse_region_encounters(data, known_templates={"goblin"}, known_regions={"darkwood"})

        assert "darkwood" in encounters
        entry = encounters["darkwood"][0]
        assert entry.template_id == "goblin"
        assert entry.chance == 0.4
        assert entry.count_min == 1
        assert entry.count_max == 3

    def test_parse_region_encounter_unknown_template_raises(self) -> None:
        from dnd_simulator.content_loader import parse_region_encounters

        data = {"darkwood": [{"template": "dragon", "chance": 0.5, "count": [1, 1]}]}
        with pytest.raises(RuntimeError, match="dragon"):
            parse_region_encounters(data, known_templates={"goblin"}, known_regions={"darkwood"})

    def test_parse_region_encounter_unknown_region_raises(self) -> None:
        from dnd_simulator.content_loader import parse_region_encounters

        data = {"mordor": [{"template": "goblin", "chance": 0.5, "count": [1, 1]}]}
        with pytest.raises(RuntimeError, match="mordor"):
            parse_region_encounters(data, known_templates={"goblin"}, known_regions={"darkwood"})


class TestLoadMonstersYaml:
    """Full load of monsters.yaml from directory-format world."""

    def test_load_monsters_from_directory(self, tmp_path: Path) -> None:
        from dnd_simulator.content_loader import load_monsters

        monsters_yaml = {
            "templates": {
                "goblin": {
                    "name": {"en": "Goblin", "ru": "Гоблин"},
                    "hp": 7,
                    "ac": 15,
                    "speed": 30,
                    "ability_scores": {"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
                    "attacks": [
                        {"name": "scimitar", "ability": "dex", "damage": [{"dice": "1d6", "type": "slashing"}]}
                    ],
                    "cr": 0.25,
                },
            },
            "encounters": {
                "dark_forest": [
                    {"template": "goblin", "chance": 0.3, "count": [1, 3]},
                ],
            },
        }
        world_dir = tmp_path / "test_world"
        world_dir.mkdir()
        (world_dir / "monsters.yaml").write_text(yaml.dump(monsters_yaml, allow_unicode=True))

        templates, encounters, region_encounters = load_monsters(world_dir, lang="en")

        assert "goblin" in templates
        assert templates["goblin"].hp == 7
        assert "dark_forest" in encounters
        assert encounters["dark_forest"][0].template_id == "goblin"
        # No region_encounters in this world → empty, location table unaffected.
        assert region_encounters == {}

    def test_load_monsters_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """Worlds without monsters.yaml are valid — return empty dicts."""
        from dnd_simulator.content_loader import load_monsters

        world_dir = tmp_path / "empty_world"
        world_dir.mkdir()

        templates, encounters, region_encounters = load_monsters(world_dir, lang="en")

        assert templates == {}
        assert encounters == {}
        assert region_encounters == {}

    def test_load_monsters_region_encounters(self, tmp_path: Path) -> None:
        """region_encounters loads in parallel with location encounters, keyed by region."""
        from dnd_simulator.content_loader import load_monsters

        monsters_yaml = {
            "templates": {
                "goblin": {
                    "name": {"en": "Goblin"},
                    "hp": 7,
                    "ac": 15,
                    "speed": 30,
                    "ability_scores": {"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
                    "attacks": [
                        {"name": "scimitar", "ability": "dex", "damage": [{"dice": "1d6", "type": "slashing"}]}
                    ],
                    "cr": 0.25,
                },
            },
            "encounters": {
                "forest_road": [{"template": "goblin", "chance": 0.3, "count": [1, 2]}],
            },
            "region_encounters": {
                "darkwood": [{"template": "goblin", "chance": 0.4, "count": [1, 3]}],
            },
        }
        world_dir = tmp_path / "region_world"
        world_dir.mkdir()
        (world_dir / "monsters.yaml").write_text(yaml.dump(monsters_yaml, allow_unicode=True))

        _templates, encounters, region_encounters = load_monsters(world_dir, lang="en", known_regions={"darkwood"})

        assert "forest_road" in encounters  # location table still present
        assert "darkwood" in region_encounters
        entry = region_encounters["darkwood"][0]
        assert entry.template_id == "goblin"
        assert entry.count_max == 3

    def test_load_monsters_region_encounters_unknown_region_raises(self, tmp_path: Path) -> None:
        """A region_encounters key naming an unknown region fails fast at load."""
        from dnd_simulator.content_loader import load_monsters

        monsters_yaml = {
            "templates": {
                "goblin": {
                    "name": {"en": "Goblin"},
                    "hp": 7,
                    "ac": 15,
                    "speed": 30,
                    "ability_scores": {"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
                    "attacks": [
                        {"name": "scimitar", "ability": "dex", "damage": [{"dice": "1d6", "type": "slashing"}]}
                    ],
                    "cr": 0.25,
                },
            },
            "region_encounters": {
                "no_such_region": [{"template": "goblin", "chance": 0.4, "count": [1, 3]}],
            },
        }
        world_dir = tmp_path / "bad_region_world"
        world_dir.mkdir()
        (world_dir / "monsters.yaml").write_text(yaml.dump(monsters_yaml, allow_unicode=True))

        with pytest.raises(RuntimeError, match="no_such_region"):
            load_monsters(world_dir, lang="en", known_regions={"darkwood"})
