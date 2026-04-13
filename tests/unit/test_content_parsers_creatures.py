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
            "gold": 1000,
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

    def test_combat_position_non_multiple_of_five_raises(self) -> None:
        """Per canonical coord convention, combat_position is in feet (multiples of 5).
        Values like [6, 5] — a common author mistake (using cell indices) — must fail fast.
        """
        npc_data = {"name": {"en": "Misplaced"}, "combat_position": [6, 5]}
        with pytest.raises(ValidationError):
            NpcContent.model_validate(npc_data)

    def test_combat_position_wrong_length_raises(self) -> None:
        npc_data = {"name": {"en": "Misplaced"}, "combat_position": [10]}
        with pytest.raises(ValidationError):
            NpcContent.model_validate(npc_data)

    def test_combat_position_negative_raises(self) -> None:
        npc_data = {"name": {"en": "Misplaced"}, "combat_position": [-5, 10]}
        with pytest.raises(ValidationError):
            NpcContent.model_validate(npc_data)

    def test_combat_position_valid_feet_ok(self) -> None:
        npc_data = {"name": {"en": "OK"}, "combat_position": [25, 30]}
        model = NpcContent.model_validate(npc_data)
        assert model.combat_position == [25, 30]

    def test_player_combat_position_non_multiple_of_five_raises(self) -> None:
        pdata = {"name": {"en": "Bad"}, "combat_position": [5, 5, 0]}
        with pytest.raises(ValidationError):
            PlayerContent.model_validate(pdata)

    def test_combat_position_round_trip_to_battle_map(self) -> None:
        """YAML combat_position in feet must land at the same Position on the battle map
        after start_combat. Pins the canonical (x, y in feet) convention.
        """
        from collections import defaultdict

        from dnd_simulator.content_loader.creatures import _to_npc, parse_player
        from dnd_simulator.core.combat import Position
        from dnd_simulator.core.models import Event
        from dnd_simulator.layers.entities.combat_manager import CombatManager

        npc_data = {
            "name": {"en": "Pinner"},
            "start_location": "arena",
            "combat_position": [15, 20],
            "faction": "monsters",
            "attacks": [{"name": "fist", "ability": "str", "damage": [{"dice": "1d4", "type": "bludgeoning"}]}],
        }
        npc_model = NpcContent.model_validate(npc_data)
        npc = _to_npc("pinner", npc_model, "en")
        npc.location_id = "arena"

        pdata = {
            "name": {"en": "Hero"},
            "start_location": "arena",
            "combat_position": [25, 30],
        }
        player = parse_player(pdata)
        player.location_id = "arena"
        player.faction_id = "kingdom"

        entities: dict[str, object] = {npc.id: npc, player.id: player}
        log: dict[str, list[Event]] = defaultdict(list)
        cm = CombatManager(entities, log)  # type: ignore[arg-type]
        combat = cm.start_combat("arena")
        assert combat is not None

        assert combat.battle_map.positions[npc.id] == Position(15, 20)
        assert combat.battle_map.positions[player.id] == Position(25, 30)


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

    @pytest.fixture()
    def npcs(self, tmp_path: Path) -> list[object]:
        from dnd_simulator.layers.entities.models import Npc
        from dnd_simulator.service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        store = JsonFileStore(tmp_path / "saves")
        svc = GameService(store=store, content_dir=Path("content"))
        session = svc.start_game(world_name="sword_vale", lang="en")
        entities_layer = session.world.layers[-1]
        all_entities = list(entities_layer._entities.values())  # type: ignore[attr-defined]
        return [e for e in all_entities if isinstance(e, Npc)]

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
        assert edgar.equipped_weapon is not None  # catalog warhammer

    # ------------------------------------------------------------------
    # Fighter NPC: Ser Aldric
    # ------------------------------------------------------------------

    def test_fighter_npc_class_features(self, npcs: list[object]) -> None:
        from dnd_simulator.core.class_features import FighterFeatures, FightingStyle

        aldric = next(n for n in npcs if n.id == "aldric")  # type: ignore[union-attr]
        assert aldric.char_class == CharClass.FIGHTER
        assert len(aldric.class_features) == 1
        feat = aldric.class_features[0]
        assert isinstance(feat, FighterFeatures)
        assert feat.fighting_style == FightingStyle.DEFENSE

    def test_fighter_npc_catalog_weapon(self, npcs: list[object]) -> None:
        aldric = next(n for n in npcs if n.id == "aldric")  # type: ignore[union-attr]
        assert aldric.equipped_weapon is not None
        assert aldric.equipped_weapon.weapon_def is not None
        assert aldric.equipped_weapon.weapon_def.weapon_id == "longsword"

    def test_fighter_npc_catalog_armor(self, npcs: list[object]) -> None:
        aldric = next(n for n in npcs if n.id == "aldric")  # type: ignore[union-attr]
        assert aldric.equipped_armor is not None
        assert aldric.equipped_armor.armor_def is not None
        assert aldric.equipped_armor.armor_def.armor_id == "chain_mail"
        assert aldric.equipped_armor.armor_def.base_ac == 16

    def test_fighter_npc_catalog_shield(self, npcs: list[object]) -> None:
        aldric = next(n for n in npcs if n.id == "aldric")  # type: ignore[union-attr]
        assert aldric.equipped_shield is not None
        assert aldric.equipped_shield.shield_def is not None
        assert aldric.equipped_shield.shield_def.ac_bonus == 2

    def test_fighter_npc_resource_pools(self, npcs: list[object]) -> None:
        aldric = next(n for n in npcs if n.id == "aldric")  # type: ignore[union-attr]
        pool_ids = [p.id for p in aldric.resource_pools]
        assert "second_wind" in pool_ids

    def test_fighter_npc_ability_scores(self, npcs: list[object]) -> None:
        from dnd_simulator.core.character import Ability

        aldric = next(n for n in npcs if n.id == "aldric")  # type: ignore[union-attr]
        assert aldric.ability_scores[Ability.STR] == 16

    # ------------------------------------------------------------------
    # Rogue NPC: Lira
    # ------------------------------------------------------------------

    def test_rogue_npc_class_features(self, npcs: list[object]) -> None:
        from dnd_simulator.core.class_features import RogueFeatures

        lira = next(n for n in npcs if n.id == "lira")  # type: ignore[union-attr]
        assert lira.char_class == CharClass.ROGUE
        assert len(lira.class_features) == 1
        feat = lira.class_features[0]
        assert isinstance(feat, RogueFeatures)
        assert feat.sneak_attack_dice == 1

    def test_rogue_npc_finesse_weapon(self, npcs: list[object]) -> None:
        lira = next(n for n in npcs if n.id == "lira")  # type: ignore[union-attr]
        assert lira.equipped_weapon is not None
        assert lira.equipped_weapon.weapon_def is not None
        assert lira.equipped_weapon.weapon_def.weapon_id == "rapier"
        assert lira.equipped_weapon.weapon_def.is_finesse is True

    def test_rogue_npc_light_armor(self, npcs: list[object]) -> None:
        lira = next(n for n in npcs if n.id == "lira")  # type: ignore[union-attr]
        assert lira.equipped_armor is not None
        assert lira.equipped_armor.armor_def is not None
        assert lira.equipped_armor.armor_def.armor_id == "studded_leather"
        assert lira.equipped_armor.armor_def.category == "light"

    def test_rogue_npc_dex_focused(self, npcs: list[object]) -> None:
        from dnd_simulator.core.character import Ability

        lira = next(n for n in npcs if n.id == "lira")  # type: ignore[union-attr]
        assert lira.ability_scores[Ability.DEX] >= 16

    # ------------------------------------------------------------------
    # Rodrik upgrade: Fighter class + catalog equipment
    # ------------------------------------------------------------------

    def test_rodrik_fighter_class(self, npcs: list[object]) -> None:
        from dnd_simulator.core.class_features import FighterFeatures, FightingStyle

        rodrik = next(n for n in npcs if n.id == "rodrik")  # type: ignore[union-attr]
        assert rodrik.char_class == CharClass.FIGHTER
        assert len(rodrik.class_features) == 1
        feat = rodrik.class_features[0]
        assert isinstance(feat, FighterFeatures)
        assert feat.fighting_style == FightingStyle.DUELING

    def test_rodrik_catalog_longsword(self, npcs: list[object]) -> None:
        rodrik = next(n for n in npcs if n.id == "rodrik")  # type: ignore[union-attr]
        assert rodrik.equipped_weapon is not None
        assert rodrik.equipped_weapon.weapon_def is not None
        assert rodrik.equipped_weapon.weapon_def.weapon_id == "longsword"

    def test_rodrik_catalog_armor_and_shield(self, npcs: list[object]) -> None:
        rodrik = next(n for n in npcs if n.id == "rodrik")  # type: ignore[union-attr]
        assert rodrik.equipped_armor is not None
        assert rodrik.equipped_armor.armor_def is not None
        assert rodrik.equipped_armor.armor_def.armor_id == "chain_mail"
        assert rodrik.equipped_shield is not None
        assert rodrik.equipped_shield.shield_def is not None

    def test_rodrik_no_inline_attacks(self, npcs: list[object]) -> None:
        """Rodrik should use catalog weapon, not inline attack definitions."""
        rodrik = next(n for n in npcs if n.id == "rodrik")  # type: ignore[union-attr]
        assert len(rodrik.attacks) == 0

    def test_rodrik_resource_pools(self, npcs: list[object]) -> None:
        rodrik = next(n for n in npcs if n.id == "rodrik")  # type: ignore[union-attr]
        pool_ids = [p.id for p in rodrik.resource_pools]
        assert "second_wind" in pool_ids

    # ------------------------------------------------------------------
    # Edgar upgrade: catalog warhammer
    # ------------------------------------------------------------------

    def test_edgar_catalog_warhammer(self, npcs: list[object]) -> None:
        edgar = next(n for n in npcs if n.id == "edgar")  # type: ignore[union-attr]
        assert edgar.equipped_weapon is not None
        assert edgar.equipped_weapon.weapon_def is not None
        assert edgar.equipped_weapon.weapon_def.weapon_id == "warhammer"

    def test_edgar_no_inline_attacks(self, npcs: list[object]) -> None:
        """Edgar should use catalog weapon, not inline attack definitions."""
        edgar = next(n for n in npcs if n.id == "edgar")  # type: ignore[union-attr]
        assert len(edgar.attacks) == 0

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
