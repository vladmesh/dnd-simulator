"""Tests for Pydantic content models (content_loader/schemas.py).

Covers: construction from minimal/full dicts, enum validation,
JSON Schema enum values + defaults, alias handling, nested models,
and model_dump round-trips.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dnd_simulator.content_loader.schemas import (
    AbilityScoresContent,
    AttackContent,
    ConnectionContent,
    DamageComponentContent,
    EncounterEntryContent,
    ItemContent,
    LeaderContent,
    LocationContent,
    MonsterTemplateContent,
    NationContent,
    NeighborContent,
    NpcContent,
    NpcMemoryContent,
    PlayerContent,
    RegionContent,
    SettlementContent,
    SquadContent,
)

# ---------------------------------------------------------------------------
# 1. Each model constructs from minimal dict — defaults fill in
# ---------------------------------------------------------------------------


class TestMinimalConstruction:
    """Provide only required fields; verify defaults fill in correctly."""

    def test_damage_component(self) -> None:
        m = DamageComponentContent(dice="1d6", type="slashing")
        assert m.dice == "1d6"
        assert m.type.value == "slashing"

    def test_attack(self) -> None:
        m = AttackContent(name="Bite", damage=[{"dice": "1d6", "type": "piercing"}])
        assert m.ability.value == "str"
        assert m.reach == 5
        assert m.is_finesse is False

    def test_ability_scores(self) -> None:
        m = AbilityScoresContent()
        assert m.str_ == 10
        assert m.dex == 10
        assert m.con == 10
        assert m.int_ == 10
        assert m.wis == 10
        assert m.cha == 10

    def test_npc_memory(self) -> None:
        m = NpcMemoryContent()
        assert m.tags == []
        assert m.recent == ""
        assert m.inner_state == ""
        assert m.current_conversation == ""

    def test_connection(self) -> None:
        m = ConnectionContent(target="highfield", direction="e")
        assert m.target == "highfield"
        assert m.direction.value == "e"

    def test_region(self) -> None:
        m = RegionContent(
            name={"en": "Coast"},
            latitude=45.0,
            longitude=-2.0,
            elevation=5,
            terrain="coast",
        )
        assert m.terrain.value == "coast"
        assert m.water_proximity == 0.0
        assert m.connections == []

    def test_neighbor(self) -> None:
        m = NeighborContent(target="market", distance=200)
        assert m.target == "market"

    def test_location(self) -> None:
        m = LocationContent(name={"en": "Town"}, region="silverport")
        assert m.settlement == ""
        assert m.description == {}
        assert m.neighbors == []

    def test_leader(self) -> None:
        m = LeaderContent(name={"en": "King"}, age=52, trait="merchant")
        assert m.trait.value == "merchant"

    def test_nation(self) -> None:
        m = NationContent(name={"en": "Kingdom"})
        assert m.regions == []
        assert m.wealth == 50.0
        assert m.military == 50.0
        assert m.stability == 70.0
        assert m.leader is None

    def test_settlement(self) -> None:
        m = SettlementContent(name={"en": "Town"}, region="silverport", type="town")
        assert m.population == 100
        assert m.prosperity == 50.0
        assert m.defenses == 30.0

    def test_monster_template(self) -> None:
        m = MonsterTemplateContent(
            name={"en": "Goblin"},
            hp=7,
            ac=15,
            speed=30,
            cr=0.25,
        )
        assert m.ability_scores.str_ == 10
        assert m.attacks == []
        assert m.faction == ""

    def test_encounter_entry(self) -> None:
        m = EncounterEntryContent(template="goblin", chance=0.4, count=[1, 3])
        assert m.count == [1, 3]

    def test_squad(self) -> None:
        m = SquadContent(
            name={"en": "Patrol"},
            faction="kingdom",
            type="patrol",
            behavior="patrol",
            start_location="road_1",
            strength=3,
        )
        assert m.route == []
        assert m.territory == []
        assert m.max_strength == 3
        assert m.members == []
        assert m.tick_interval == 3600

    def test_npc_minimal(self) -> None:
        m = NpcContent(name={"en": "Guard"})
        assert m.race.value == "human"
        assert m.char_class.value == "commoner"
        assert m.hp == 4
        assert m.ac == 10
        assert m.speed == 30
        assert m.ai == "rule_based"
        assert m.gold == 0

    def test_player_minimal(self) -> None:
        m = PlayerContent(name={"en": "Hero"})
        assert m.race.value == "human"
        assert m.char_class.value == "fighter"
        assert m.hp == 10
        assert m.level == 1
        assert m.alignment.value == "true_neutral"


# ---------------------------------------------------------------------------
# 2. Each model constructs from full dict — all values preserved
# ---------------------------------------------------------------------------


class TestFullConstruction:
    """Provide all fields with non-default values; verify all preserved."""

    def test_npc_full(self) -> None:
        m = NpcContent(
            name={"en": "Blacksmith", "ru": "Кузнец"},
            race="dwarf",
            char_class="fighter",
            role="blacksmith",
            start_location="forge",
            settlement_id="iron_town",
            faction="dwarves",
            personality={"en": "Grumpy", "ru": "Ворчливый"},
            hp=20,
            ac=14,
            speed=25,
            gold=50,
            ai="llm",
            attacks=[
                {
                    "name": "Hammer",
                    "ability": "str",
                    "damage": [{"dice": "1d8", "type": "bludgeoning"}],
                    "reach": 5,
                }
            ],
            items=[
                {
                    "name": "Hammer",
                    "type": "weapon",
                    "weapon_id": "hammer",
                    "category": "simple",
                    "attack_name": "Hammer Strike",
                    "damage": [{"dice": "1d8", "type": "bludgeoning"}],
                }
            ],
            ability_scores={"str": 16, "dex": 10, "con": 14, "int": 10, "wis": 12, "cha": 8},
            class_features={"fighting_style": "defense"},
            memory={"tags": ["angry"], "recent": "Was robbed", "inner_state": "furious", "current_conversation": ""},
        )
        assert m.race.value == "dwarf"
        assert m.char_class.value == "fighter"
        assert m.role.value == "blacksmith"
        assert m.hp == 20
        assert m.gold == 50
        assert m.ai == "llm"
        assert len(m.attacks) == 1
        assert m.attacks[0].damage[0].type.value == "bludgeoning"
        assert m.ability_scores.str_ == 16  # type: ignore[union-attr]
        assert m.memory.tags == ["angry"]  # type: ignore[union-attr]

    def test_player_full(self) -> None:
        m = PlayerContent(
            name={"en": "Hero", "ru": "Герой"},
            race="elf",
            char_class="rogue",
            level=5,
            alignment="chaotic_good",
            appearance={"en": "Tall and lean"},
            start_location="tavern",
            faction="guild",
            hp=25,
            ac=15,
            gold=1000,
            attacks=[{"name": "Dagger", "damage": [{"dice": "1d4", "type": "piercing"}]}],
            items=[],
            ability_scores={"str": 8, "dex": 18, "con": 12, "int": 14, "wis": 10, "cha": 13},
        )
        assert m.race.value == "elf"
        assert m.char_class.value == "rogue"
        assert m.level == 5
        assert m.alignment.value == "chaotic_good"
        assert m.hp == 25

    def test_region_full(self) -> None:
        m = RegionContent(
            name={"en": "Forest", "ru": "Лес"},
            latitude=50.0,
            longitude=10.0,
            elevation=200,
            terrain="forest",
            water_proximity=0.3,
            connections=[{"target": "plains_region", "direction": "s"}],
            battle_map={"width": 80, "height": 80, "walls": [[0, 0, 10, 0]]},
        )
        assert m.terrain.value == "forest"
        assert m.water_proximity == 0.3
        assert len(m.connections) == 1
        assert m.connections[0].direction.value == "s"

    def test_squad_full(self) -> None:
        m = SquadContent(
            name={"en": "Bandits"},
            faction="outlaws",
            type="bandit",
            behavior="raid",
            start_location="camp",
            route=["road_1", "road_2"],
            territory=["forest_clearing"],
            strength=5,
            max_strength=8,
            members=["bandit", "bandit", "bandit_leader"],
            tick_interval=1800,
        )
        assert m.type.value == "bandit"
        assert m.behavior.value == "raid"
        assert m.max_strength == 8
        assert len(m.members) == 3


# ---------------------------------------------------------------------------
# 3. Enum validation rejects bad values
# ---------------------------------------------------------------------------


class TestEnumValidation:
    """Invalid enum values must raise ValidationError."""

    def test_region_bad_terrain(self) -> None:
        with pytest.raises(ValidationError):
            RegionContent(name={"en": "X"}, latitude=0, longitude=0, elevation=0, terrain="lava")

    def test_npc_bad_race(self) -> None:
        with pytest.raises(ValidationError):
            NpcContent(name={"en": "X"}, race="alien")

    def test_npc_bad_class(self) -> None:
        with pytest.raises(ValidationError):
            NpcContent(name={"en": "X"}, char_class="necromancer")

    def test_connection_bad_direction(self) -> None:
        with pytest.raises(ValidationError):
            ConnectionContent(target="x", direction="up")

    def test_settlement_bad_type(self) -> None:
        with pytest.raises(ValidationError):
            SettlementContent(name={"en": "X"}, region="r", type="metropolis")

    def test_leader_bad_trait(self) -> None:
        with pytest.raises(ValidationError):
            LeaderContent(name={"en": "X"}, age=30, trait="tyrant")

    def test_squad_bad_type(self) -> None:
        with pytest.raises(ValidationError):
            SquadContent(
                name={"en": "X"},
                faction="f",
                type="army",
                behavior="patrol",
                start_location="l",
                strength=1,
            )

    def test_damage_component_bad_type(self) -> None:
        with pytest.raises(ValidationError):
            DamageComponentContent(dice="1d6", type="plasma")


# ---------------------------------------------------------------------------
# 4. JSON Schema contains enum values
# ---------------------------------------------------------------------------


class TestJsonSchemaEnums:
    """model_json_schema() must expose enum values."""

    def test_region_terrain_enum_in_schema(self) -> None:
        schema = RegionContent.model_json_schema()
        terrain_schema = schema["properties"]["terrain"]
        # Could be inline or a $ref — resolve either way
        enum_values = _extract_enum(schema, terrain_schema)
        assert "coast" in enum_values
        assert "forest" in enum_values
        assert "mountains" in enum_values

    def test_npc_race_enum_in_schema(self) -> None:
        schema = NpcContent.model_json_schema()
        race_schema = schema["properties"]["race"]
        enum_values = _extract_enum(schema, race_schema)
        assert "human" in enum_values
        assert "elf" in enum_values
        assert "dwarf" in enum_values

    def test_npc_class_enum_in_schema(self) -> None:
        schema = NpcContent.model_json_schema()
        class_schema = schema["properties"]["class"]
        enum_values = _extract_enum(schema, class_schema)
        assert "fighter" in enum_values
        assert "rogue" in enum_values

    def test_monster_template_has_no_missing_enums(self) -> None:
        """MonsterTemplateContent schema should be generatable without error."""
        schema = MonsterTemplateContent.model_json_schema()
        assert "properties" in schema


# ---------------------------------------------------------------------------
# 5. JSON Schema contains defaults
# ---------------------------------------------------------------------------


class TestJsonSchemaDefaults:
    """JSON Schema must include default values for optional fields."""

    def test_npc_hp_default(self) -> None:
        schema = NpcContent.model_json_schema()
        assert schema["properties"]["hp"]["default"] == 4

    def test_npc_race_default(self) -> None:
        schema = NpcContent.model_json_schema()
        race_prop = schema["properties"]["race"]
        # Default could be in the property or in a $ref
        default = race_prop.get("default")
        if default is None and "$ref" in race_prop:
            default = race_prop.get("default")
        assert default == "human"

    def test_player_hp_default(self) -> None:
        schema = PlayerContent.model_json_schema()
        assert schema["properties"]["hp"]["default"] == 10

    def test_settlement_population_default(self) -> None:
        schema = SettlementContent.model_json_schema()
        assert schema["properties"]["population"]["default"] == 100


# ---------------------------------------------------------------------------
# 6. Alias works for "class" field
# ---------------------------------------------------------------------------


class TestClassAlias:
    """The 'class' YAML key must work via alias for 'char_class' field."""

    def test_npc_class_from_alias(self) -> None:
        m = NpcContent.model_validate({"name": {"en": "X"}, "class": "fighter"})
        assert m.char_class.value == "fighter"

    def test_npc_class_from_field_name(self) -> None:
        m = NpcContent.model_validate({"name": {"en": "X"}, "char_class": "rogue"})
        assert m.char_class.value == "rogue"

    def test_player_class_from_alias(self) -> None:
        m = PlayerContent.model_validate({"name": {"en": "X"}, "class": "wizard"})
        assert m.char_class.value == "wizard"

    def test_dump_by_alias_uses_class(self) -> None:
        m = NpcContent(name={"en": "X"}, char_class="fighter")
        dumped = m.model_dump(by_alias=True)
        assert "class" in dumped
        assert "char_class" not in dumped


# ---------------------------------------------------------------------------
# 7. Nested models validate
# ---------------------------------------------------------------------------


class TestNestedModels:
    """Nested structures are parsed and validated correctly."""

    def test_npc_with_attacks(self) -> None:
        m = NpcContent(
            name={"en": "X"},
            attacks=[
                {
                    "name": "Bite",
                    "ability": "str",
                    "damage": [{"dice": "1d6", "type": "piercing"}],
                }
            ],
        )
        assert len(m.attacks) == 1
        assert isinstance(m.attacks[0], AttackContent)
        assert isinstance(m.attacks[0].damage[0], DamageComponentContent)
        assert m.attacks[0].damage[0].type.value == "piercing"

    def test_npc_with_items(self) -> None:
        m = NpcContent(
            name={"en": "X"},
            items=[
                {
                    "name": "Longsword",
                    "type": "weapon",
                    "weapon_id": "longsword",
                    "category": "martial",
                    "attack_name": "Slash",
                    "damage": [{"dice": "1d8", "type": "slashing"}],
                }
            ],
        )
        assert len(m.items) == 1
        assert isinstance(m.items[0], ItemContent)
        assert m.items[0].type.value == "weapon"

    def test_npc_with_memory(self) -> None:
        m = NpcContent(
            name={"en": "X"},
            memory={
                "tags": ["angry", "hates:orcs"],
                "recent": "Lost a fight",
                "inner_state": "vengeful",
                "current_conversation": "",
            },
        )
        assert isinstance(m.memory, NpcMemoryContent)
        assert m.memory.tags == ["angry", "hates:orcs"]

    def test_region_with_connections(self) -> None:
        m = RegionContent(
            name={"en": "X"},
            latitude=0,
            longitude=0,
            elevation=0,
            terrain="plains",
            connections=[
                {"target": "forest", "direction": "n"},
                {"target": "coast", "direction": "w"},
            ],
        )
        assert len(m.connections) == 2
        assert all(isinstance(c, ConnectionContent) for c in m.connections)

    def test_nation_with_leader(self) -> None:
        m = NationContent(
            name={"en": "X"},
            leader={"name": {"en": "King"}, "age": 55, "trait": "diplomat"},
        )
        assert isinstance(m.leader, LeaderContent)
        assert m.leader.trait.value == "diplomat"

    def test_location_with_neighbors(self) -> None:
        m = LocationContent(
            name={"en": "X"},
            region="r",
            neighbors=[{"target": "market", "distance": 200}],
        )
        assert len(m.neighbors) == 1
        assert isinstance(m.neighbors[0], NeighborContent)


# ---------------------------------------------------------------------------
# 8. model_dump round-trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """construct → model_dump(by_alias=True) → model_validate → identical."""

    def _round_trip(self, model_cls: type, data: dict) -> None:
        original = model_cls.model_validate(data)
        dumped = original.model_dump(by_alias=True)
        restored = model_cls.model_validate(dumped)
        assert original == restored

    def test_npc_round_trip(self) -> None:
        self._round_trip(
            NpcContent,
            {
                "name": {"en": "Guard"},
                "race": "human",
                "class": "fighter",
                "role": "guard",
                "hp": 15,
                "attacks": [{"name": "Sword", "damage": [{"dice": "1d8", "type": "slashing"}]}],
            },
        )

    def test_player_round_trip(self) -> None:
        self._round_trip(
            PlayerContent,
            {
                "name": {"en": "Hero"},
                "race": "elf",
                "class": "rogue",
                "level": 3,
                "alignment": "chaotic_good",
            },
        )

    def test_region_round_trip(self) -> None:
        self._round_trip(
            RegionContent,
            {
                "name": {"en": "Forest"},
                "latitude": 50.0,
                "longitude": 10.0,
                "elevation": 200,
                "terrain": "forest",
                "connections": [{"target": "plains", "direction": "s"}],
            },
        )

    def test_settlement_round_trip(self) -> None:
        self._round_trip(
            SettlementContent,
            {
                "name": {"en": "Town"},
                "region": "silverport",
                "type": "town",
                "population": 500,
            },
        )

    def test_nation_round_trip(self) -> None:
        self._round_trip(
            NationContent,
            {
                "name": {"en": "Kingdom"},
                "leader": {"name": {"en": "King"}, "age": 55, "trait": "diplomat"},
                "regions": ["r1", "r2"],
            },
        )

    def test_squad_round_trip(self) -> None:
        self._round_trip(
            SquadContent,
            {
                "name": {"en": "Patrol"},
                "faction": "kingdom",
                "type": "patrol",
                "behavior": "patrol",
                "start_location": "road",
                "strength": 3,
                "members": ["soldier"],
            },
        )

    def test_monster_template_round_trip(self) -> None:
        self._round_trip(
            MonsterTemplateContent,
            {
                "name": {"en": "Goblin"},
                "hp": 7,
                "ac": 15,
                "speed": 30,
                "cr": 0.25,
                "attacks": [{"name": "Scimitar", "ability": "dex", "damage": [{"dice": "1d6", "type": "slashing"}]}],
            },
        )

    def test_location_round_trip(self) -> None:
        self._round_trip(
            LocationContent,
            {
                "name": {"en": "Market"},
                "region": "silverport",
                "settlement": "silverport_city",
                "neighbors": [{"target": "dock", "distance": 100}],
            },
        )

    def test_item_round_trip(self) -> None:
        self._round_trip(
            ItemContent,
            {
                "name": "Healing Potion",
                "type": "potion",
                "heal_dice": "2d4+2",
                "price": 50,
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_enum(schema: dict, prop: dict) -> list[str]:
    """Extract enum values from a JSON Schema property (inline or $ref)."""
    if "enum" in prop:
        return prop["enum"]
    if "allOf" in prop:
        for sub in prop["allOf"]:
            if "$ref" in sub:
                ref_name = sub["$ref"].split("/")[-1]
                return schema.get("$defs", {}).get(ref_name, {}).get("enum", [])
    if "$ref" in prop:
        ref_name = prop["$ref"].split("/")[-1]
        return schema.get("$defs", {}).get(ref_name, {}).get("enum", [])
    # anyOf pattern (used when there's a default)
    if "anyOf" in prop:
        for sub in prop["anyOf"]:
            result = _extract_enum(schema, sub)
            if result:
                return result
    return []
