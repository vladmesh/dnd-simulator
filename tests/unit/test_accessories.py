"""Tests for accessory equipment slots with modifier effects.

Product-level tests: equip accessories → verify stat changes via modifier pipeline.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Character, CharClass, Race
from dnd_simulator.core.items import (
    AccessoryDef,
    ArmorCategory,
    ArmorDef,
    EquipmentSlot,
    Item,
    ItemType,
    ShieldDef,
)
from dnd_simulator.core.models import ActionResult, Event
from dnd_simulator.core.modifiers import Modifier, ModifierOp, StatType
from dnd_simulator.core.world import World
from dnd_simulator.rules.modifiers import effective_ac, effective_speed
from dnd_simulator.rules.validation import ActionContext
from dnd_simulator.service.action_dispatcher import create_dispatcher


def _noop_emit(event: Event) -> ActionResult:
    return ActionResult()


_WORLD = cast(World, MagicMock(spec=World))
_PEACEFUL = ActionContext(is_combat=False, current_turn_entity_id="pc")


def _pc(**kwargs: object) -> Character:
    defaults = dict(
        id="pc",
        name="Hero",
        location_id="loc",
        char_class=CharClass.FIGHTER,
        race=Race.HUMAN,
        level=1,
    )
    defaults.update(kwargs)
    return Character(**defaults)  # type: ignore[arg-type]


def _ring_of_protection() -> Item:
    return Item(
        id="ring_prot_0",
        name="Ring of Protection",
        item_type=ItemType.ACCESSORY,
        accessory_def=AccessoryDef(
            accessory_id="ring_of_protection",
            slot=EquipmentSlot.RING,
            grant_modifiers=(Modifier(StatType.AC, ModifierOp.ADD, value=1, source="ring_of_protection"),),
        ),
    )


def _boots_of_striding() -> Item:
    return Item(
        id="boots_stride_0",
        name="Boots of Striding",
        item_type=ItemType.ACCESSORY,
        accessory_def=AccessoryDef(
            accessory_id="boots_of_striding",
            slot=EquipmentSlot.FEET,
            grant_modifiers=(Modifier(StatType.SPEED, ModifierOp.ADD, value=5, source="boots_of_striding"),),
        ),
    )


def _iron_helmet() -> Item:
    return Item(
        id="iron_helm_0",
        name="Iron Helmet",
        item_type=ItemType.ACCESSORY,
        accessory_def=AccessoryDef(
            accessory_id="iron_helmet",
            slot=EquipmentSlot.HEAD,
            grant_modifiers=(Modifier(StatType.AC, ModifierOp.ADD, value=1, source="iron_helmet"),),
        ),
    )


def _chain_mail() -> Item:
    return Item(
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


def _shield() -> Item:
    return Item(
        id="shield_0",
        name="Shield",
        item_type=ItemType.SHIELD,
        shield_def=ShieldDef(shield_id="shield", ac_bonus=2),
    )


class TestAccessoryModifiers:
    def test_ring_of_protection_grants_ac(self) -> None:
        """Ring of Protection (+1 AC): equip → AC +1, unequip → back to base."""
        pc = _pc()
        ring = _ring_of_protection()
        pc.inventory.append(ring)
        base_ac = effective_ac(pc)

        d = create_dispatcher(_WORLD)
        result = d.dispatch(pc, Action(name=ActionType.EQUIP_RING, params={"ring_id": ring.id}), _PEACEFUL, _noop_emit)
        assert result.success
        assert effective_ac(pc) == base_ac + 1

        result = d.dispatch(pc, Action(name=ActionType.UNEQUIP_RING), _PEACEFUL, _noop_emit)
        assert result.success
        assert effective_ac(pc) == base_ac

    def test_boots_of_striding_grant_speed(self) -> None:
        """Boots of Striding (+5 speed): equip → speed +5, unequip → back to 30."""
        pc = _pc()
        boots = _boots_of_striding()
        pc.inventory.append(boots)

        assert effective_speed(pc) == 30
        d = create_dispatcher(_WORLD)
        result = d.dispatch(pc, Action(name=ActionType.EQUIP_FEET, params={"feet_id": boots.id}), _PEACEFUL, _noop_emit)
        assert result.success
        assert effective_speed(pc) == 35

        result = d.dispatch(pc, Action(name=ActionType.UNEQUIP_FEET), _PEACEFUL, _noop_emit)
        assert result.success
        assert effective_speed(pc) == 30

    def test_helmet_stacks_with_armor(self) -> None:
        """Iron Helmet (+1 AC) stacks with chain mail (base 16) → AC 17."""
        pc = _pc()
        armor = _chain_mail()
        helmet = _iron_helmet()
        pc.equipped_armor = armor
        pc.inventory.append(helmet)

        assert effective_ac(pc) == 16
        d = create_dispatcher(_WORLD)
        result = d.dispatch(
            pc, Action(name=ActionType.EQUIP_HEAD, params={"head_id": helmet.id}), _PEACEFUL, _noop_emit
        )
        assert result.success
        assert effective_ac(pc) == 17

    def test_full_stack_armor_shield_ring(self) -> None:
        """Chain mail (16) + shield (+2) + ring (+1) → AC 19."""
        pc = _pc()
        pc.equipped_armor = _chain_mail()
        pc.equipped_shield = _shield()
        ring = _ring_of_protection()
        pc.inventory.append(ring)

        d = create_dispatcher(_WORLD)
        result = d.dispatch(pc, Action(name=ActionType.EQUIP_RING, params={"ring_id": ring.id}), _PEACEFUL, _noop_emit)
        assert result.success
        assert effective_ac(pc) == 19  # 16 base + 2 shield + 1 ring

    def test_wrong_slot_rejected(self) -> None:
        """Cannot equip a ring into the head slot."""
        pc = _pc()
        ring = _ring_of_protection()
        pc.inventory.append(ring)

        d = create_dispatcher(_WORLD)
        # Try to equip ring as head gear — should fail (wrong item type check via slot config)
        result = d.dispatch(pc, Action(name=ActionType.EQUIP_HEAD, params={"head_id": ring.id}), _PEACEFUL, _noop_emit)
        assert not result.success
        assert pc.equipped_head is None  # type: ignore[attr-defined]


class TestContentLoaderAccessories:
    def test_parse_accessory_from_yaml(self) -> None:
        """YAML accessory with equipped: true → creature has it in slot, not inventory."""
        from dnd_simulator.content_loader import parse_items

        items_data = [
            {
                "name": "Ring of Protection",
                "type": "accessory",
                "accessory_id": "ring_of_protection",
                "slot": "ring",
                "modifiers": [{"stat": "ac", "op": "add", "value": 1, "source": "ring_of_protection"}],
                "equipped": True,
            },
            {
                "name": "Iron Helmet",
                "type": "accessory",
                "accessory_id": "iron_helmet",
                "slot": "head",
                "modifiers": [{"stat": "ac", "op": "add", "value": 1, "source": "iron_helmet"}],
            },
        ]
        items = parse_items(items_data)
        assert len(items) == 2

        ring = items[0]
        assert ring.item_type == ItemType.ACCESSORY
        assert ring.accessory_def is not None
        assert ring.accessory_def.slot == EquipmentSlot.RING
        assert len(ring.accessory_def.grant_modifiers) == 1
        assert ring.accessory_def.grant_modifiers[0].stat == StatType.AC
        assert ring.params.get("equipped") is True

        helmet = items[1]
        assert helmet.accessory_def is not None
        assert helmet.accessory_def.slot == EquipmentSlot.HEAD
        assert helmet.params.get("equipped") is not True


class TestAwarenessAccessories:
    def test_describe_accessory(self) -> None:
        """Accessory description shows modifier effects."""
        from dnd_simulator.core.awareness import describe_item

        ring = _ring_of_protection()
        desc = describe_item(ring)
        assert "Ring of Protection" in desc
        assert "+1" in desc
        assert "AC" in desc or "ac" in desc.lower()
