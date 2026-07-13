"""Tests for QueryHandler extracted from EntitiesLayer."""

from __future__ import annotations

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    CharClass,
    DamageComponent,
    DamageType,
    NpcRole,
    Race,
)
from dnd_simulator.core.combat import BattleMap
from dnd_simulator.core.events import EntitySayPayload
from dnd_simulator.core.items import EquipmentSlot, Item, ItemType, WeaponCategory, WeaponDef
from dnd_simulator.core.models import Event, EventType, Query, QueryType
from dnd_simulator.core.player import PlayerCharacter
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


class TestEntitiesAtLocation:
    """ENTITIES_AT_LOCATION query returns correct entities at a given location."""

    def test_returns_entities_at_requested_location(self) -> None:
        c1 = Character(id="c1", name="Alice", location_id="tavern", ability_scores=_scores(STR=14))
        c2 = Character(id="c2", name="Bob", location_id="tavern", ability_scores=_scores(STR=12))
        c3 = Character(id="c3", name="Carol", location_id="market")

        layer = EntitiesLayer([c1, c2, c3])

        result = layer.query(
            Query(question=QueryType.ENTITIES_AT_LOCATION, params={"location_id": "tavern", "hour": 12})
        )
        entities = result.value
        assert isinstance(entities, list)
        assert len(entities) == 2
        names = {e["name"] for e in entities}
        assert names == {"Alice", "Bob"}

    def test_summary_has_required_fields(self) -> None:
        c = Character(id="c1", name="Hero", location_id="square", ability_scores=_scores(STR=16))
        layer = EntitiesLayer([c])

        result = layer.query(
            Query(question=QueryType.ENTITIES_AT_LOCATION, params={"location_id": "square", "hour": 12})
        )
        summary = result.value[0]
        assert summary["id"] == "c1"
        assert summary["name"] == "Hero"


class TestEntityInfo:
    """ENTITY_INFO query returns full detail for a character."""

    def test_character_detail_has_race_class_hp_ac(self) -> None:
        player = PlayerCharacter(
            id="p1",
            name="Bron",
            location_id="tavern",
            ability_scores=_scores(STR=16, DEX=14, CON=12),
            attacks=(_SWORD,),
            race=Race.DWARF,
            char_class=CharClass.FIGHTER,
            level=3,
        )
        layer = EntitiesLayer([player])

        result = layer.query(Query(question=QueryType.ENTITY_INFO, params={"entity_id": "p1"}))
        detail = result.value
        assert isinstance(detail, dict)
        assert detail["id"] == "p1"
        assert detail["name"] == "Bron"
        assert detail["race"] == Race.DWARF.value
        assert detail["char_class"] == CharClass.FIGHTER.value
        assert detail["level"] == 3
        assert "hp" in detail
        assert "max_hp" in detail
        assert "ac" in detail
        assert detail["entity_type"] == "player"


class TestNpcInfo:
    """NPC_INFO query includes personality and AI type."""

    def test_npc_info_has_personality_and_ai_type(self) -> None:
        npc = Npc(
            id="smith",
            name="Edgar",
            location_id="forge",
            role=NpcRole.BLACKSMITH,
            personality="Gruff but fair.",
            settlement_id="silverport",
            ai_type="llm",
        )
        layer = EntitiesLayer([npc])

        result = layer.query(Query(question=QueryType.NPC_INFO, params={"npc_id": "smith"}))
        detail = result.value
        assert isinstance(detail, dict)
        assert detail["id"] == "smith"
        assert detail["name"] == "Edgar"
        assert detail["role"] == NpcRole.BLACKSMITH.value
        assert detail["personality"] == "Gruff but fair."
        assert detail["ai_type"] == "llm"
        assert "hp" in detail
        assert "ac" in detail


class TestCombatInfo:
    """COMBAT_INFO query returns battle state."""

    def test_combat_info_returns_initiative_and_positions(self) -> None:
        c1 = Character(id="c1", name="Fighter", location_id="arena", ability_scores=_scores(STR=16, DEX=14))
        c2 = Character(id="c2", name="Rogue", location_id="arena", ability_scores=_scores(DEX=18))

        battle_map = BattleMap(width=10, height=10)

        layer = EntitiesLayer([c1, c2], battle_map_configs={"arena": battle_map})
        layer._combat.start_combat("arena")

        result = layer.query(Query(question=QueryType.COMBAT_INFO, params={"location_id": "arena"}))
        info = result.value
        assert isinstance(info, dict)
        assert "round_number" in info
        assert "turn_order" in info
        assert "positions" in info
        assert len(info["turn_order"]) == 2


class TestPerceivedLog:
    """PERCEIVED_LOG query filters events by observer."""

    def test_perceived_log_returns_only_visible_events(self) -> None:
        observer = Character(id="obs", name="Observer", location_id="square", ability_scores=_scores(WIS=14))
        other = Character(id="other", name="Other", location_id="square")

        layer = EntitiesLayer([observer, other])

        # Add events to location log — one visible to all, one private to "other"
        public_event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data=EntitySayPayload(**{"entity_id": "other", "text": "Hello everyone!"}),
            observer_ids=None,
        )
        private_event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data=EntitySayPayload(**{"entity_id": "other", "text": "Secret whisper"}),
            observer_ids=frozenset({"other"}),
        )
        layer._location_log["square"].append(public_event)
        layer._location_log["square"].append(private_event)

        result = layer.query(Query(question=QueryType.PERCEIVED_LOG, params={"entity_id": "obs"}))
        perceived = result.value
        assert isinstance(perceived, list)
        # Observer should see the public event but not the private one
        assert len(perceived) == 1
        assert "Hello everyone" in perceived[0]


class TestCreatureInventoryInDetail:
    """ENTITY_INFO and ALL_CREATURES return inventory and equipment."""

    _WEAPON_DEF = WeaponDef(
        weapon_id="longsword",
        attack_name="Longsword Strike",
        category=WeaponCategory.MARTIAL,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )
    _WEAPON_ITEM = Item(
        id="longsword_0",
        name="Longsword",
        item_type=ItemType.WEAPON,
        weapon_def=_WEAPON_DEF,
    )
    _POTION_ITEM = Item(
        id="heal_pot_0",
        name="Healing Potion",
        item_type=ItemType.POTION,
        params={"heal_dice": "2d4+2"},
    )

    def test_entity_info_includes_inventory_and_equipped_weapon(self) -> None:
        player = PlayerCharacter(
            id="p1",
            name="Bron",
            location_id="tavern",
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
            race=Race.DWARF,
            char_class=CharClass.FIGHTER,
            level=3,
            inventory=[self._POTION_ITEM],
            equipped={EquipmentSlot.WEAPON: self._WEAPON_ITEM},
        )
        layer = EntitiesLayer([player])

        result = layer.query(Query(question=QueryType.ENTITY_INFO, params={"entity_id": "p1"}))
        detail = result.value
        assert isinstance(detail, dict)

        # Inventory
        inv = detail["inventory"]
        assert isinstance(inv, list)
        assert len(inv) == 1
        assert inv[0]["id"] == "heal_pot_0"
        assert inv[0]["name"] == "Healing Potion"
        assert inv[0]["item_type"] == "potion"

        # Equipped weapon
        weapon = detail["equipped_weapon"]
        assert isinstance(weapon, dict)
        assert weapon["weapon_id"] == "longsword"
        assert weapon["attack_name"] == "Longsword Strike"
        assert weapon["damage"] == "1d8 slashing"

    def test_entity_info_no_equipment_returns_empty_and_null(self) -> None:
        char = Character(
            id="c1",
            name="Naked",
            location_id="road",
            ability_scores=_scores(STR=10),
        )
        layer = EntitiesLayer([char])

        result = layer.query(Query(question=QueryType.ENTITY_INFO, params={"entity_id": "c1"}))
        detail = result.value
        assert detail["inventory"] == []
        assert detail["equipped_weapon"] is None

    def test_all_creatures_includes_inventory(self) -> None:
        char = Character(
            id="c1",
            name="Armed",
            location_id="camp",
            ability_scores=_scores(STR=14),
            inventory=[self._POTION_ITEM],
            equipped={EquipmentSlot.WEAPON: self._WEAPON_ITEM},
        )
        layer = EntitiesLayer([char])

        result = layer.query(Query(question=QueryType.ALL_CREATURES, params={}))
        creatures = result.value
        assert len(creatures) == 1
        assert "inventory" in creatures[0]
        assert "equipped_weapon" in creatures[0]
