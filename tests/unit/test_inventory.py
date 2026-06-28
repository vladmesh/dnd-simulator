"""Tests for the shared item-transfer primitive (`rules/inventory.py`)."""

from __future__ import annotations

from dnd_simulator.core.character import AbilityScores
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.rules.inventory import transfer_items


def _item(item_id: str, name: str) -> Item:
    return Item(id=item_id, name=name, item_type=ItemType.WEAPON)


def _holder(*, gold: int = 0, items: list[Item] | None = None) -> PlayerCharacter:
    pc = PlayerCharacter(id="h", name="Holder", location_id="loc", gold=gold)
    if items is not None:
        pc.inventory = items
    return pc


class TestTransferItems:
    def test_moves_items_and_gold_from_src_to_dst(self) -> None:
        sword, shield, potion = _item("sword", "Sword"), _item("shield", "Shield"), _item("potion", "Potion")
        a = _holder(gold=30, items=[sword, shield, potion])
        b = _holder(gold=10, items=[])

        transfer_items(src=a, dst=b, items=[sword, potion], gold=30)

        assert a.inventory == [shield]
        assert a.gold == 0
        assert b.inventory == [sword, potion]
        assert b.gold == 40

    def test_zero_gold_default_moves_only_items(self) -> None:
        gem = _item("gem", "Gem")
        a = _holder(gold=5, items=[gem])
        b = _holder(gold=5, items=[])

        transfer_items(src=a, dst=b, items=[gem])

        assert a.inventory == []
        assert b.inventory == [gem]
        assert a.gold == 5
        assert b.gold == 5

    def test_gold_only_transfer_leaves_inventory_untouched(self) -> None:
        coin_purse = _item("purse", "Purse")
        a = _holder(gold=100, items=[coin_purse])
        b = _holder(gold=0, items=[])

        transfer_items(src=a, dst=b, items=[], gold=60)

        assert a.gold == 40
        assert b.gold == 60
        assert a.inventory == [coin_purse]
        assert b.inventory == []

    def test_bare_monster_creature_is_a_holder(self) -> None:
        # gold lives on Creature now, so a spawned monster (bare Creature, not Character)
        # is a uniform InventoryHolder defaulting to 0 gold.
        template = MonsterTemplate(
            id="goblin",
            name="Goblin",
            hp=7,
            ac=13,
            speed=30,
            ability_scores=AbilityScores(),
            attacks=(),
            cr=0.25,
        )
        goblin = template.spawn(location_id="cave", instance_id="goblin_1")
        assert goblin.gold == 0

        player = _holder(gold=50, items=[])
        transfer_items(src=player, dst=goblin, items=[], gold=20)
        assert goblin.gold == 20
        assert player.gold == 30
