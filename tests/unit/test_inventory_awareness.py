"""Tests for inventory & equipment awareness (Sprint 003, Phase 2, Task 1)."""

from __future__ import annotations

from dnd_simulator.content_loader import parse_items
from dnd_simulator.core.awareness import (
    ItemInfo,
    describe_item,
)
from dnd_simulator.core.items import EquipmentSlot, Item, ItemType
from dnd_simulator.round import Round

# ---------------------------------------------------------------------------
# Test 1: Item with price round-trips through content loader
# ---------------------------------------------------------------------------


class TestItemPrice:
    def test_parse_item_with_price(self) -> None:
        items = parse_items([{"name": "Healing Potion", "type": "potion", "heal_dice": "2d4+2", "price": 50}])
        assert len(items) == 1
        assert items[0].price == 50

    def test_parse_item_without_price(self) -> None:
        items = parse_items([{"name": "Healing Potion", "type": "potion", "heal_dice": "2d4+2"}])
        assert len(items) == 1
        assert items[0].price is None


# ---------------------------------------------------------------------------
# Test 2: Equipped items visible in awareness
# ---------------------------------------------------------------------------


def _make_creature_with_equipment() -> object:
    """Create a Creature with a sword equipped and a ring equipped."""
    from dnd_simulator.core.character import (
        AbilityScores,
        Creature,
        DamageComponent,
        DamageType,
    )
    from dnd_simulator.core.items import (
        AccessoryDef,
        WeaponCategory,
        WeaponDef,
    )
    from dnd_simulator.core.modifiers import Modifier, ModifierOp, StatType

    sword = Item(
        id="longsword_0",
        name="Longsword",
        item_type=ItemType.WEAPON,
        weapon_def=WeaponDef(
            weapon_id="longsword",
            attack_name="sword slash",
            category=WeaponCategory.MARTIAL,
            damage=(DamageComponent(dice="1d8", type=DamageType.SLASHING),),
        ),
    )
    ring = Item(
        id="ring_of_protection_0",
        name="Ring of Protection",
        item_type=ItemType.ACCESSORY,
        accessory_def=AccessoryDef(
            accessory_id="ring_of_protection",
            slot=EquipmentSlot.RING,
            grant_modifiers=(Modifier(stat=StatType.AC, op=ModifierOp.ADD, value=1, source="ring_of_protection"),),
        ),
    )
    creature = Creature(
        id="test_creature",
        name="Test",
        location_id="loc",
        ability_scores=AbilityScores(),
        max_hp=20,
        current_hp=20,
        ac=10,
        equipped_weapon=sword,
        equipped_ring=ring,
    )
    return creature


class TestEquippedAwareness:
    def test_build_equipped_returns_equipped_items(self) -> None:
        creature = _make_creature_with_equipment()
        assert isinstance(creature, object)
        from dnd_simulator.core.character import Creature

        assert isinstance(creature, Creature)
        equipped = Round._build_equipped(creature)
        assert len(equipped) == 2
        slots = {e.slot for e in equipped}
        assert EquipmentSlot.WEAPON in slots
        assert EquipmentSlot.RING in slots

        weapon_info = next(e for e in equipped if e.slot == EquipmentSlot.WEAPON)
        assert weapon_info.item_id == "longsword_0"
        assert weapon_info.name == "Longsword"

    def test_build_equipped_empty_slots_absent(self) -> None:
        from dnd_simulator.core.character import AbilityScores, Creature

        creature = Creature(
            id="bare",
            name="Bare",
            location_id="loc",
            ability_scores=AbilityScores(),
            max_hp=10,
            current_hp=10,
            ac=10,
        )
        equipped = Round._build_equipped(creature)
        assert equipped == []


# ---------------------------------------------------------------------------
# Test 3: Full inventory always in awareness (not gated by action)
# ---------------------------------------------------------------------------


class TestFullInventoryAwareness:
    def test_inventory_visible_without_use_item_action(self) -> None:
        potion = Item(
            id="potion_0",
            name="Healing Potion",
            item_type=ItemType.POTION,
            params={"heal_dice": "2d4+2"},
            price=50,
        )
        sword = Item(
            id="sword_0",
            name="Sword",
            item_type=ItemType.WEAPON,
            price=100,
        )
        scroll = Item(
            id="scroll_0",
            name="Scroll",
            item_type=ItemType.POTION,
            params={"heal_dice": "1d4"},
        )
        from dnd_simulator.core.character import AbilityScores, Creature

        creature = Creature(
            id="c",
            name="C",
            location_id="loc",
            ability_scores=AbilityScores(),
            max_hp=10,
            current_hp=10,
            ac=10,
            inventory=[potion, sword, scroll],
        )
        # No USE_ITEM or EQUIP in available_actions — should still return all items
        items = Round._build_available_items(creature, [])
        assert len(items) == 3
        assert all(isinstance(i, ItemInfo) for i in items)


# ---------------------------------------------------------------------------
# Test 4: _player_to_dict includes equipment and inventory
# ---------------------------------------------------------------------------


class TestPlayerToDict:
    def test_includes_equipped_and_inventory(self) -> None:
        from dnd_simulator.core.items import ArmorCategory, ArmorDef
        from dnd_simulator.core.player import PlayerCharacter

        chain_mail = Item(
            id="chain_mail_0",
            name="Chain Mail",
            item_type=ItemType.ARMOR,
            armor_def=ArmorDef(
                armor_id="chain_mail",
                category=ArmorCategory.HEAVY,
                base_ac=16,
                max_dex_bonus=0,
            ),
        )
        potion = Item(
            id="potion_0",
            name="Healing Potion",
            item_type=ItemType.POTION,
            params={"heal_dice": "2d4+2"},
            price=50,
        )

        from dnd_simulator.core.character import AbilityScores, Alignment, CharClass, Race

        player = PlayerCharacter(
            id="player_1",
            name="Hero",
            location_id="loc",
            race=Race.HUMAN,
            char_class=CharClass.FIGHTER,
            alignment=Alignment.TRUE_NEUTRAL,
            ability_scores=AbilityScores(),
            max_hp=20,
            current_hp=20,
            ac=16,
            equipped_armor=chain_mail,
            inventory=[potion],
        )

        from dnd_simulator.service.session import build_player_status

        status = build_player_status(player)
        # Must have equipped list
        assert any(e["slot"] == "armor" for e in status.equipped)
        assert status.equipped[0]["name"] == "Chain Mail"

        # Must have inventory list
        assert len(status.inventory) == 1
        assert status.inventory[0]["name"] == "Healing Potion"
        assert status.inventory[0]["price"] == 50


# ---------------------------------------------------------------------------
# Test 5: ItemInfo includes price
# ---------------------------------------------------------------------------


class TestItemInfoPrice:
    def test_item_info_with_price(self) -> None:
        item = Item(
            id="potion_0",
            name="Healing Potion",
            item_type=ItemType.POTION,
            params={"heal_dice": "2d4+2"},
            price=50,
        )
        info = ItemInfo(id=item.id, name=item.name, description=describe_item(item), price=item.price)
        assert info.price == 50

    def test_item_info_without_price(self) -> None:
        item = Item(
            id="potion_0",
            name="Healing Potion",
            item_type=ItemType.POTION,
            params={"heal_dice": "2d4+2"},
        )
        info = ItemInfo(id=item.id, name=item.name, description=describe_item(item), price=item.price)
        assert info.price is None
