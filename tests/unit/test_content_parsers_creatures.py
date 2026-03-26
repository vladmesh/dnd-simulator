"""Tests for creature, monster, and item parsers rewritten to use Pydantic content models.

Covers: round-trip for NPCs/monsters/squads/items/player,
validation errors, and full start_game integration.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dnd_simulator.content_loader.catalogs import load_catalog
from dnd_simulator.content_loader.schemas import (
    ItemContent,
    MonsterTemplateContent,
    NpcContent,
    PlayerContent,
    SquadContent,
)
from dnd_simulator.core.character import (
    Ability,
    CharClass,
    NpcRole,
    Race,
)
from dnd_simulator.core.items import ItemType
from dnd_simulator.core.squad import SquadBehavior, SquadType

ENTITIES_PATH = Path("content/library/entities/sword_vale")
ECOLOGY_PATH = Path("content/library/ecology/sword_vale")
MONSTER_CATALOG_PATH = Path("content/catalogs/monsters")


# ---------------------------------------------------------------------------
# 1. Round-trip: NPC with full equipment
# ---------------------------------------------------------------------------


class TestNpcFullRoundTrip:
    """Parse NPC dict with weapon, armor, shield, items, attacks, ability scores, memory, class features."""

    def test_full_npc_round_trip(self) -> None:
        from dnd_simulator.content_loader.creatures import parse_npc

        npc_data: dict[str, object] = {
            "name": {"en": "Sir Galahad", "ru": "Сэр Галахад"},
            "race": "human",
            "class": "fighter",
            "role": "guard",
            "start_location": "castle_gate",
            "settlement_id": "castle",
            "faction": "kingdom",
            "personality": {"en": "Brave and loyal"},
            "hp": 30,
            "ac": 18,
            "speed": 30,
            "gold": 100,
            "ai": "rule_based",
            "ability_scores": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 13, "cha": 11},
            "attacks": [
                {
                    "name": "longsword",
                    "ability": "str",
                    "damage": [{"dice": "1d8", "type": "slashing"}],
                    "reach": 5,
                }
            ],
            "items": [
                {
                    "name": "Longsword",
                    "type": "weapon",
                    "weapon_id": "longsword",
                    "category": "martial",
                    "attack_name": "longsword strike",
                    "damage": [{"dice": "1d8", "type": "slashing"}],
                    "equipped": True,
                },
                {
                    "name": "Chain Mail",
                    "type": "armor",
                    "armor_id": "chain_mail",
                    "category": "heavy",
                    "base_ac": 16,
                    "max_dex_bonus": 0,
                    "equipped": True,
                },
                {
                    "name": "Shield",
                    "type": "shield",
                    "shield_id": "shield",
                    "ac_bonus": 2,
                    "equipped": True,
                },
            ],
            "class_features": {"fighting_style": "defense"},
            "memory": {
                "tags": ["loyal", "brave"],
                "recent": "Defended the gate",
                "inner_state": "Vigilant",
                "current_conversation": "",
            },
        }

        # Validate via Pydantic model
        model = NpcContent.model_validate(npc_data)
        assert model.race == Race.HUMAN
        assert model.char_class == CharClass.FIGHTER
        assert model.role == NpcRole.GUARD
        assert model.hp == 30
        assert model.ability_scores.str_ == 16
        assert len(model.attacks) == 1
        assert len(model.items) == 3
        assert model.memory is not None
        assert model.memory.tags == ["loyal", "brave"]

        # Parse to runtime Npc
        npc = parse_npc("galahad", npc_data, lang="en")
        assert npc.id == "galahad"
        assert npc.name == "Sir Galahad"
        assert npc.race == Race.HUMAN
        assert npc.char_class == CharClass.FIGHTER
        assert npc.max_hp == 30
        assert npc.equipped_weapon is not None
        assert npc.equipped_weapon.name == "Longsword"
        assert npc.equipped_armor is not None
        assert npc.equipped_armor.name == "Chain Mail"
        assert npc.equipped_shield is not None
        assert npc.equipped_shield.name == "Shield"
        assert npc.ability_scores[Ability.STR] == 16
        assert len(npc.attacks) == 1
        assert npc.memory.tags == ["loyal", "brave"]
        assert len(npc.class_features) == 1  # FighterFeatures


# ---------------------------------------------------------------------------
# 2. Round-trip: NPC with minimal fields
# ---------------------------------------------------------------------------


class TestNpcMinimal:
    """NPC with just a name → defaults applied correctly."""

    def test_minimal_npc_defaults(self) -> None:
        from dnd_simulator.content_loader.creatures import parse_npc

        npc_data: dict[str, object] = {"name": {"en": "Peasant"}}

        model = NpcContent.model_validate(npc_data)
        assert model.race == Race.HUMAN
        assert model.char_class == CharClass.COMMONER
        assert model.hp == 4
        assert model.ac == 10
        assert model.role == NpcRole.COMMONER
        assert model.ai == "rule_based"

        npc = parse_npc("peasant", npc_data, lang="en")
        assert npc.name == "Peasant"
        assert npc.race == Race.HUMAN
        assert npc.max_hp == 4
        assert npc.ac == 10


# ---------------------------------------------------------------------------
# 3. Round-trip: monster templates from sword_vale
# ---------------------------------------------------------------------------


class TestMonsterTemplatesRoundTrip:
    """Load sword_vale monsters.yaml → MonsterTemplateContent → runtime MonsterTemplate."""

    def test_load_monsters_returns_templates(self) -> None:
        from dnd_simulator.content_loader.monsters import load_monsters

        catalog = load_catalog(MONSTER_CATALOG_PATH, MonsterTemplateContent)
        templates, _encounters = load_monsters(ECOLOGY_PATH, lang="en", catalog=catalog)
        assert len(templates) > 0
        assert "goblin" in templates
        assert "wolf" in templates
        assert "bandit" in templates

    def test_monster_template_fields(self) -> None:
        from dnd_simulator.content_loader.monsters import load_monsters

        catalog = load_catalog(MONSTER_CATALOG_PATH, MonsterTemplateContent)
        templates, _ = load_monsters(ECOLOGY_PATH, lang="en", catalog=catalog)
        goblin = templates["goblin"]
        assert goblin.name  # non-empty
        assert goblin.hp == 7
        assert goblin.ac == 15
        assert goblin.speed == 30
        assert goblin.cr == 0.25
        assert len(goblin.attacks) > 0
        assert goblin.ability_scores[Ability.DEX] == 14

    def test_monster_template_round_trip_via_schema(self) -> None:
        """Validate raw YAML via MonsterTemplateContent, verify fields match."""
        template_data = {
            "name": {"en": "Goblin"},
            "hp": 7,
            "ac": 15,
            "speed": 30,
            "cr": 0.25,
            "faction": "goblin_tribe",
            "ability_scores": {"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8},
            "attacks": [{"name": "scimitar", "ability": "dex", "damage": [{"dice": "1d6", "type": "slashing"}]}],
        }
        model = MonsterTemplateContent.model_validate(template_data)
        assert model.hp == 7
        assert model.ac == 15
        assert model.ability_scores.dex == 14
        assert len(model.attacks) == 1
        assert model.attacks[0].name == "scimitar"

    def test_encounters_loaded(self) -> None:
        from dnd_simulator.content_loader.monsters import load_monsters

        catalog = load_catalog(MONSTER_CATALOG_PATH, MonsterTemplateContent)
        _, encounters = load_monsters(ECOLOGY_PATH, lang="en", catalog=catalog)
        assert len(encounters) > 0
        # silverport_greenwood_road has goblin + wolf encounters
        assert "silverport_greenwood_road" in encounters


# ---------------------------------------------------------------------------
# 4. Round-trip: squads from sword_vale
# ---------------------------------------------------------------------------


class TestSquadsRoundTrip:
    """Load sword_vale squads.yaml → SquadContent → runtime Squad."""

    def test_load_squads_returns_nonempty(self) -> None:
        from dnd_simulator.content_loader.monsters import load_squads

        squads = load_squads(ECOLOGY_PATH, lang="en")
        assert len(squads) > 0

    def test_squad_fields(self) -> None:
        from dnd_simulator.content_loader.monsters import load_squads

        squads = load_squads(ECOLOGY_PATH, lang="en")
        patrol = squads["kingdom_patrol_1"]
        assert patrol.name  # non-empty
        assert patrol.squad_type == SquadType.PATROL
        assert patrol.behavior == SquadBehavior.PATROL
        assert patrol.strength == 5
        assert patrol.max_strength == 5
        assert len(patrol.route) == 3
        assert len(patrol.member_templates) == 3

    def test_squad_round_trip_via_schema(self) -> None:
        squad_data = {
            "name": {"en": "Test Squad"},
            "faction": "test",
            "type": "patrol",
            "behavior": "patrol",
            "start_location": "loc_a",
            "strength": 3,
            "route": ["loc_a", "loc_b"],
            "members": ["goblin"],
        }
        model = SquadContent.model_validate(squad_data)
        assert model.strength == 3
        assert model.max_strength == 3  # defaults to strength
        assert model.type == SquadType.PATROL


# ---------------------------------------------------------------------------
# 5. Round-trip: items
# ---------------------------------------------------------------------------


class TestItemsRoundTrip:
    """Parse weapon, armor, shield, potion, accessory → model_dump → re-validate → identical."""

    def test_weapon_round_trip(self) -> None:
        weapon_data = {
            "name": "Longsword",
            "type": "weapon",
            "weapon_id": "longsword",
            "category": "martial",
            "attack_name": "longsword strike",
            "damage": [{"dice": "1d8", "type": "slashing"}],
            "equipped": True,
        }
        model = ItemContent.model_validate(weapon_data)
        assert model.type == ItemType.WEAPON
        assert model.weapon_id == "longsword"
        assert model.category == "martial"
        dumped = model.model_dump()
        revalidated = ItemContent.model_validate(dumped)
        assert revalidated.weapon_id == model.weapon_id

    def test_armor_round_trip(self) -> None:
        armor_data = {
            "name": "Chain Mail",
            "type": "armor",
            "armor_id": "chain_mail",
            "category": "heavy",
            "base_ac": 16,
        }
        model = ItemContent.model_validate(armor_data)
        assert model.type == ItemType.ARMOR
        dumped = model.model_dump()
        revalidated = ItemContent.model_validate(dumped)
        assert revalidated.armor_id == model.armor_id

    def test_shield_round_trip(self) -> None:
        shield_data = {"name": "Shield", "type": "shield", "shield_id": "shield", "ac_bonus": 2}
        model = ItemContent.model_validate(shield_data)
        assert model.type == ItemType.SHIELD
        dumped = model.model_dump()
        revalidated = ItemContent.model_validate(dumped)
        assert revalidated.shield_id == model.shield_id

    def test_potion_round_trip(self) -> None:
        potion_data = {"name": "Health Potion", "type": "potion", "heal_dice": "2d4+2", "price": 50}
        model = ItemContent.model_validate(potion_data)
        assert model.type == ItemType.POTION
        assert model.heal_dice == "2d4+2"
        dumped = model.model_dump()
        revalidated = ItemContent.model_validate(dumped)
        assert revalidated.heal_dice == model.heal_dice

    def test_accessory_round_trip(self) -> None:
        acc_data = {
            "name": "Iron Helmet",
            "type": "accessory",
            "accessory_id": "iron_helmet",
            "slot": "head",
            "modifiers": [{"stat": "ac", "op": "add", "value": 1, "source": "iron_helmet"}],
        }
        model = ItemContent.model_validate(acc_data)
        assert model.type == ItemType.ACCESSORY
        dumped = model.model_dump()
        revalidated = ItemContent.model_validate(dumped)
        assert revalidated.accessory_id == model.accessory_id


# ---------------------------------------------------------------------------
# 6. Validation error on bad NPC data
# ---------------------------------------------------------------------------


class TestNpcValidationErrors:
    """Bad NPC data must produce clear Pydantic ValidationError."""

    def test_bad_race_raises_validation_error(self) -> None:
        npc_data = {"name": {"en": "Bad"}, "race": "robot"}
        with pytest.raises(ValidationError):
            NpcContent.model_validate(npc_data)

    def test_bad_class_raises_validation_error(self) -> None:
        npc_data = {"name": {"en": "Bad"}, "class": "jedi"}
        with pytest.raises(ValidationError):
            NpcContent.model_validate(npc_data)

    def test_bad_role_raises_validation_error(self) -> None:
        npc_data = {"name": {"en": "Bad"}, "role": "spaceman"}
        with pytest.raises(ValidationError):
            NpcContent.model_validate(npc_data)


# ---------------------------------------------------------------------------
# 7. Validation error on bad item type
# ---------------------------------------------------------------------------


class TestItemValidationErrors:
    """Bad item data must produce clear Pydantic ValidationError."""

    def test_bad_item_type_raises_validation_error(self) -> None:
        item_data = {"name": "Bad", "type": "spaceship"}
        with pytest.raises(ValidationError):
            ItemContent.model_validate(item_data)


# ---------------------------------------------------------------------------
# 8. Player parse matches current behavior
# ---------------------------------------------------------------------------


class TestPlayerRoundTrip:
    """Parse player dict through PlayerContent → convert → same result as current parse_player."""

    def test_player_round_trip(self) -> None:
        from dnd_simulator.content_loader.creatures import parse_player

        pdata: dict[str, object] = {
            "id": "player_test",
            "name": {"en": "Hero"},
            "race": "elf",
            "class": "rogue",
            "level": 3,
            "alignment": "chaotic_good",
            "appearance": {"en": "Tall and mysterious"},
            "start_location": "tavern",
            "hp": 25,
            "ac": 14,
            "gold": 50,
            "ability_scores": {"str": 10, "dex": 16, "con": 12, "int": 14, "wis": 11, "cha": 13},
            "attacks": [{"name": "rapier", "ability": "dex", "damage": [{"dice": "1d8", "type": "piercing"}]}],
            "items": [
                {
                    "name": "Rapier",
                    "type": "weapon",
                    "weapon_id": "rapier",
                    "category": "martial",
                    "attack_name": "rapier thrust",
                    "damage": [{"dice": "1d8", "type": "piercing"}],
                    "is_finesse": True,
                    "equipped": True,
                }
            ],
        }

        # Validate via Pydantic
        model = PlayerContent.model_validate(pdata)
        assert model.race == Race.ELF
        assert model.char_class == CharClass.ROGUE
        assert model.level == 3

        # Parse to runtime PlayerCharacter
        player = parse_player(pdata, lang="en")
        assert player.id == "player_test"
        assert player.name == "Hero"
        assert player.race == Race.ELF
        assert player.char_class == CharClass.ROGUE
        assert player.max_hp == 25
        assert player.equipped_weapon is not None
        assert player.equipped_weapon.name == "Rapier"
        assert player.ability_scores[Ability.DEX] == 16
        assert len(player.class_features) == 1  # RogueFeatures

    def test_player_minimal_defaults(self) -> None:
        from dnd_simulator.content_loader.creatures import parse_player

        pdata: dict[str, object] = {"name": {"en": "Adventurer"}}
        player = parse_player(pdata, lang="en")
        assert player.name == "Adventurer"
        assert player.race == Race.HUMAN
        assert player.char_class == CharClass.FIGHTER
        assert player.max_hp == 10


# ---------------------------------------------------------------------------
# 9. sword_vale full load integration
# ---------------------------------------------------------------------------


class TestSwordValeFullLoad:
    """GameService.start_game('sword_vale') → session works, NPCs present with correct stats."""

    def test_start_game_npcs_present(self, tmp_path: Path) -> None:
        from dnd_simulator.layers.entities.models import Npc
        from dnd_simulator.service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        store = JsonFileStore(tmp_path / "saves")
        svc = GameService(store=store, content_dir=Path("content"))
        session = svc.start_game(world_name="sword_vale", lang="en")

        assert session is not None
        assert session.world is not None

        # Get entities layer — access internal _entities
        entities_layer = session.world.layers[-1]  # entities is last
        all_entities = list(entities_layer._entities.values())  # type: ignore[attr-defined]
        npcs = [e for e in all_entities if isinstance(e, Npc)]
        assert len(npcs) > 0

        # Check Edgar has correct stats
        edgar = next((n for n in npcs if n.id == "edgar"), None)
        assert edgar is not None
        assert edgar.name == "Edgar the Smith"
        assert edgar.max_hp == 18
        assert edgar.ac == 12
        assert len(edgar.attacks) > 0

    def test_start_game_squads_loaded(self, tmp_path: Path) -> None:
        from dnd_simulator.service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        store = JsonFileStore(tmp_path / "saves")
        svc = GameService(store=store, content_dir=Path("content"))
        session = svc.start_game(world_name="sword_vale", lang="en")

        # Ecology layer has squads
        ecology_layer = session.world.layers[3]  # ecology is 4th (index 3)
        state = ecology_layer.get_state()
        assert "squads" in state
        assert len(state["squads"]) > 0
