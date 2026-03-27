"""Tests for NPC description field and structured inspect data in NearbyEntity.

Sprint 009 Phase 4 Task 1: NPC Description Field + Structured Inspect Data.
"""

from __future__ import annotations

from typing import Any

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    DamageComponent,
    DamageType,
    NpcRole,
    Race,
)
from dnd_simulator.core.models import Answer, Query
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)


def _scores(**overrides: int) -> AbilityScores:
    scores = dict(AbilityScores().scores)
    for name, val in overrides.items():
        scores[Ability[name.upper()]] = val
    return AbilityScores(scores=scores)


def _null_query(target: str, query: Query) -> Answer:
    return Answer(value=None)


class TestNpcDescriptionFieldLoading:
    """NPC description field loads from YAML content and populates runtime model."""

    def test_npc_with_description_from_yaml(self) -> None:
        from dnd_simulator.content_loader.creatures import parse_npc

        data: dict[str, Any] = {
            "name": {"en": "Edgar the Smith", "ru": "Эдгар Кузнец"},
            "start_location": "smithy",
            "settlement_id": "town",
            "faction": "kingdom",
            "role": "blacksmith",
            "description": {
                "en": "A burly man with soot-stained arms.",
                "ru": "Крепкий мужчина с руками в саже.",
            },
        }
        npc = parse_npc("edgar", data, lang="en")
        assert npc.description == "A burly man with soot-stained arms."

    def test_npc_without_description_gets_empty_string(self) -> None:
        from dnd_simulator.content_loader.creatures import parse_npc

        data: dict[str, Any] = {
            "name": {"en": "Old Willow"},
            "start_location": "clearing",
            "faction": "militia",
            "role": "commoner",
        }
        npc = parse_npc("hermit", data, lang="en")
        assert npc.description == ""

    def test_npc_description_resolves_language(self) -> None:
        from dnd_simulator.content_loader.creatures import parse_npc

        data: dict[str, Any] = {
            "name": {"en": "Edgar", "ru": "Эдгар"},
            "start_location": "smithy",
            "description": {
                "en": "Burly smith.",
                "ru": "Крепкий кузнец.",
            },
        }
        npc = parse_npc("edgar", data, lang="ru")
        assert npc.description == "Крепкий кузнец."


class TestMonsterTemplateDescription:
    """MonsterTemplate carries description through to spawned creatures."""

    def test_monster_template_with_description(self) -> None:
        from dnd_simulator.content_loader.monsters import parse_monster_template

        data: dict[str, Any] = {
            "name": {"en": "Wolf"},
            "hp": 11,
            "ac": 13,
            "speed": 40,
            "cr": 0.25,
            "description": {"en": "A grey wolf with sharp fangs."},
            "attacks": [{"name": "bite", "ability": "dex", "damage": [{"dice": "1d6", "type": "piercing"}]}],
        }
        template = parse_monster_template("wolf", data, lang="en")
        assert template.description == "A grey wolf with sharp fangs."

    def test_monster_template_without_description(self) -> None:
        from dnd_simulator.content_loader.monsters import parse_monster_template

        data: dict[str, Any] = {
            "name": {"en": "Goblin"},
            "hp": 7,
            "ac": 15,
            "speed": 30,
            "cr": 0.25,
            "attacks": [{"name": "scimitar", "ability": "dex", "damage": [{"dice": "1d6", "type": "slashing"}]}],
        }
        template = parse_monster_template("goblin", data, lang="en")
        assert template.description == ""


class TestNearbyEntityStructuredFields:
    """build_nearby_entities() returns NearbyEntity with structured fields from Npc data."""

    def test_nearby_npc_has_structured_fields(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="tavern",
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
        )
        npc = Npc(
            id="marta",
            name="Marta",
            location_id="tavern",
            race=Race.HUMAN,
            role=NpcRole.TAVERN_KEEPER,
            faction_id="kingdom",
            description="A cheerful woman with rosy cheeks.",
            settlement_id="silverport",
        )

        layer = EntitiesLayer([player, npc])
        nearby = layer.build_nearby_entities(player, hour=14, query_fn=_null_query)

        assert len(nearby) == 1
        n = nearby[0]
        assert n.id == "marta"
        assert n.name == "Marta"
        assert n.race == "human"
        assert n.role == "tavern_keeper"
        assert n.faction_id == "kingdom"
        assert n.npc_description == "A cheerful woman with rosy cheeks."
        assert n.is_merchant is False

    def test_nearby_merchant_has_is_merchant_true(self) -> None:
        player = Character(
            id="p1",
            name="Hero",
            location_id="market",
        )
        merchant = Npc(
            id="gretta",
            name="Gretta",
            location_id="market",
            role=NpcRole.MERCHANT,
            description="A shrewd trader.",
        )

        layer = EntitiesLayer([player, merchant])
        nearby = layer.build_nearby_entities(player, hour=14, query_fn=_null_query)

        assert len(nearby) == 1
        assert nearby[0].is_merchant is True

    def test_nearby_non_npc_creature_has_empty_structured_fields(self) -> None:
        """Plain Creature (e.g. spawned monster) gets default empty fields."""
        from dnd_simulator.core.character import Creature

        player = Character(
            id="p1",
            name="Hero",
            location_id="road",
        )
        wolf = Creature(
            id="wolf1",
            name="Wolf",
            location_id="road",
            max_hp=11,
            current_hp=11,
        )

        layer = EntitiesLayer([player, wolf])
        nearby = layer.build_nearby_entities(player, hour=14, query_fn=_null_query)

        assert len(nearby) == 1
        n = nearby[0]
        assert n.name == "Wolf"
        assert n.race == ""
        assert n.role == ""
        assert n.npc_description == ""
        assert n.is_merchant is False
