"""Tests for faction system: faction_id on creatures, faction relations."""

from pathlib import Path

import yaml

from dnd_simulator.core.character import Ability, AbilityScores, Attack, Creature, DamageComponent, DamageType
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.layers.politics.models import FactionRelation


class TestFactionRelation:
    """Faction relation queries on PoliticsLayer."""

    def _make_politics(self, faction_relations: dict[tuple[str, str], FactionRelation] | None = None) -> object:
        from dnd_simulator.layers.politics.layer import PoliticsLayer

        layer = PoliticsLayer()
        if faction_relations:
            for (a, b), rel in faction_relations.items():
                layer.set_faction_relation(a, b, rel)
        return layer

    def test_hostile_relation(self) -> None:
        layer = self._make_politics({("kingdom", "bandits"): FactionRelation.HOSTILE})
        assert layer.get_faction_relation("kingdom", "bandits") is FactionRelation.HOSTILE

    def test_same_faction_is_friendly(self) -> None:
        layer = self._make_politics()
        assert layer.get_faction_relation("kingdom", "kingdom") is FactionRelation.FRIENDLY

    def test_unspecified_defaults_to_neutral(self) -> None:
        layer = self._make_politics()
        assert layer.get_faction_relation("kingdom", "wildlife") is FactionRelation.NEUTRAL

    def test_relation_is_symmetric(self) -> None:
        layer = self._make_politics({("kingdom", "bandits"): FactionRelation.HOSTILE})
        assert layer.get_faction_relation("bandits", "kingdom") is FactionRelation.HOSTILE

    def test_query_faction_relation(self) -> None:
        """FACTION_RELATION query through the layer query interface."""
        from dnd_simulator.core.models import Query, QueryType

        layer = self._make_politics({("kingdom", "goblin_tribe"): FactionRelation.HOSTILE})
        answer = layer.query(Query(question=QueryType.FACTION_RELATION, params={"a": "kingdom", "b": "goblin_tribe"}))
        assert answer.value is FactionRelation.HOSTILE


class TestFactionOnCreature:
    """faction_id field on Creature."""

    def test_creature_has_faction_id(self) -> None:
        c = Creature(id="guard_1", name="Guard", location_id="town", faction_id="kingdom")
        assert c.faction_id == "kingdom"

    def test_creature_default_faction_empty(self) -> None:
        c = Creature(id="blob", name="Blob", location_id="swamp")
        assert c.faction_id == ""


class TestFactionOnMonsterTemplate:
    """faction_id on MonsterTemplate and spawn propagation."""

    def test_template_has_faction_id(self) -> None:
        t = MonsterTemplate(
            id="wolf",
            name="Wolf",
            hp=11,
            ac=13,
            speed=40,
            ability_scores=AbilityScores(),
            attacks=(),
            cr=0.25,
            faction_id="wildlife",
        )
        assert t.faction_id == "wildlife"

    def test_spawn_propagates_faction_id(self) -> None:
        t = MonsterTemplate(
            id="goblin",
            name="Goblin",
            hp=7,
            ac=15,
            speed=30,
            ability_scores=AbilityScores(),
            attacks=(
                Attack(
                    name="scimitar",
                    ability=Ability.DEX,
                    damage=(DamageComponent(dice="1d6", type=DamageType.SLASHING),),
                ),
            ),
            cr=0.25,
            faction_id="goblin_tribe",
        )
        creature = t.spawn("forest", "goblin_1")
        assert creature.faction_id == "goblin_tribe"


class TestParseFactions:
    """Loading factions.yaml and parsing faction fields."""

    def test_load_factions_from_yaml(self, tmp_path: Path) -> None:
        from dnd_simulator.content_loader import load_factions

        factions_yaml = {
            "kingdom": {
                "name": {"en": "Kingdom Forces", "ru": "Силы Королевства"},
                "relations": {"bandits": "hostile", "wildlife": "neutral"},
            },
            "bandits": {
                "name": {"en": "Bandits", "ru": "Бандиты"},
                "relations": {"kingdom": "hostile"},
            },
            "wildlife": {"name": {"en": "Wildlife", "ru": "Дикие звери"}},
        }
        world_dir = tmp_path / "test_world"
        world_dir.mkdir()
        (world_dir / "factions.yaml").write_text(yaml.dump(factions_yaml, allow_unicode=True))

        faction_data = load_factions(world_dir)

        assert faction_data.relations[("bandits", "kingdom")] is FactionRelation.HOSTILE
        # Wildlife has no explicit relations → not in dict (defaults to NEUTRAL on query)
        assert ("kingdom", "wildlife") not in faction_data.relations or faction_data.relations[
            ("kingdom", "wildlife")
        ] is FactionRelation.NEUTRAL
        # Names loaded with default lang=en
        assert faction_data.names["kingdom"] == "Kingdom Forces"
        assert faction_data.names["bandits"] == "Bandits"
        assert faction_data.names["wildlife"] == "Wildlife"

    def test_load_factions_missing_file(self, tmp_path: Path) -> None:
        from dnd_simulator.content_loader import load_factions

        world_dir = tmp_path / "empty_world"
        world_dir.mkdir()
        faction_data = load_factions(world_dir)
        assert faction_data.relations == {}
        assert faction_data.names == {}

    def test_parse_npc_with_faction(self) -> None:
        from dnd_simulator.content_loader import parse_npc

        ndata = {
            "name": "Guard",
            "start_location": "town_gate",
            "role": "guard",
            "hp": 20,
            "ac": 16,
            "faction": "kingdom",
        }
        npc = parse_npc("guard_1", ndata, known_locations={"town_gate"})
        assert npc.faction_id == "kingdom"

    def test_parse_npc_without_faction(self) -> None:
        from dnd_simulator.content_loader import parse_npc

        ndata = {
            "name": "Villager",
            "start_location": "village",
            "hp": 4,
        }
        npc = parse_npc("villager_1", ndata, known_locations={"village"})
        assert npc.faction_id == ""

    def test_parse_monster_template_with_faction(self) -> None:
        from dnd_simulator.content_loader import parse_monster_template

        data = {
            "name": "Wolf",
            "hp": 11,
            "ac": 13,
            "speed": 40,
            "attacks": [{"name": "bite", "ability": "dex", "damage": [{"dice": "2d4", "type": "piercing"}]}],
            "cr": 0.25,
            "faction": "wildlife",
        }
        template = parse_monster_template("wolf", data)
        assert template.faction_id == "wildlife"

    def test_parse_monster_template_without_faction(self) -> None:
        from dnd_simulator.content_loader import parse_monster_template

        data = {"name": "Blob", "hp": 5, "ac": 8, "speed": 10, "attacks": [], "cr": 0.0}
        template = parse_monster_template("blob", data)
        assert template.faction_id == ""
