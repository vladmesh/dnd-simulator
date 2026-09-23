"""Direct tests for rules/handlers/equipment.py — slot-generic equip/unequip handlers."""

from __future__ import annotations

from typing import Any

import pytest

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Character
from dnd_simulator.core.events import EquipmentPayload
from dnd_simulator.core.items import (
    AccessoryDef,
    ArmorCategory,
    ArmorDef,
    EquipmentSlot,
    Item,
    ItemType,
    ShieldDef,
)
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.rules.handlers.equipment import EQUIPMENT_HANDLERS, SLOT_CONFIGS


def _ring(item_id: str = "ring_1") -> Item:
    return Item(
        id=item_id,
        name="Ring of Protection",
        item_type=ItemType.ACCESSORY,
        accessory_def=AccessoryDef(accessory_id="ring_of_protection", slot=EquipmentSlot.RING),
    )


def _armor(item_id: str, name: str) -> Item:
    armor_def = ArmorDef(armor_id=item_id, category=ArmorCategory.LIGHT, base_ac=11, max_dex_bonus=99)
    return Item(id=item_id, name=name, item_type=ItemType.ARMOR, armor_def=armor_def)


def _shield() -> Item:
    return Item(id="s1", name="Shield", item_type=ItemType.SHIELD, shield_def=ShieldDef(shield_id="shield", ac_bonus=2))


class _Recorder:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, event: Event) -> ActionResult:
        self.events.append(event)
        return ActionResult()


def _run(action_type: ActionType, actor: Character, **params: Any) -> tuple[ActionResult, _Recorder]:
    emit = _Recorder()
    result = EQUIPMENT_HANDLERS[action_type](actor, Action(name=action_type, params=params), emit, None, None)
    return result, emit


def test_every_slot_has_both_handlers() -> None:
    for cfg in SLOT_CONFIGS.values():
        assert cfg.equip_action in EQUIPMENT_HANDLERS
        assert cfg.unequip_action in EQUIPMENT_HANDLERS


class TestEquip:
    def test_equip_moves_item_from_bag_to_slot_and_emits(self) -> None:
        shield = _shield()
        actor = Character(id="c1", name="Hero", location_id="arena", inventory=[shield])

        result, emit = _run(ActionType.EQUIP_SHIELD, actor, shield_id="s1")

        assert result.success
        assert actor.equipped_shield is shield
        assert shield not in actor.inventory
        assert [e.event_type for e in emit.events] == [EventType.ENTITY_EQUIP]
        assert emit.events[0].payload == EquipmentPayload("c1", "Shield", "s1")

    def test_equip_swaps_the_previous_item_back_into_the_bag(self) -> None:
        old, new = _armor("leather", "Leather"), _armor("padded", "Padded")
        actor = Character(
            id="c1", name="Hero", location_id="arena", inventory=[new], equipped={EquipmentSlot.ARMOR: old}
        )

        result, _emit = _run(ActionType.EQUIP_ARMOR, actor, armor_id="padded")

        assert result.success
        assert actor.equipped_armor is new
        assert actor.inventory == [old]

    def test_equip_missing_item_fails_without_side_effects(self) -> None:
        actor = Character(id="c1", name="Hero", location_id="arena")

        result, emit = _run(ActionType.EQUIP_RING, actor, ring_id="ghost")

        assert not result.success
        assert "ghost" in (result.error or "")
        assert actor.equipped_ring is None
        assert emit.events == []

    def test_equip_wrong_item_type_fails(self) -> None:
        shield = _shield()
        actor = Character(id="c1", name="Hero", location_id="arena", inventory=[shield])

        result, emit = _run(ActionType.EQUIP_ARMOR, actor, armor_id="s1")

        assert not result.success
        assert actor.equipped_armor is None
        assert actor.inventory == [shield]
        assert emit.events == []

    @pytest.mark.parametrize(
        ("action_type", "param"), [(ActionType.EQUIP_HEAD, "head_id"), (ActionType.EQUIP_FEET, "feet_id")]
    )
    def test_accessory_into_the_wrong_slot_fails(self, action_type: ActionType, param: str) -> None:
        ring = _ring()
        actor = Character(id="c1", name="Hero", location_id="arena", inventory=[ring])

        result, emit = _run(action_type, actor, **{param: "ring_1"})

        assert not result.success
        assert actor.inventory == [ring]
        assert emit.events == []

    def test_accessory_into_its_own_slot_succeeds(self) -> None:
        ring = _ring()
        actor = Character(id="c1", name="Hero", location_id="arena", inventory=[ring])

        result, _emit = _run(ActionType.EQUIP_RING, actor, ring_id="ring_1")

        assert result.success
        assert actor.equipped_ring is ring


class TestUnequip:
    def test_unequip_returns_item_to_bag_and_emits(self) -> None:
        ring = _ring()
        actor = Character(id="c1", name="Hero", location_id="arena", equipped={EquipmentSlot.RING: ring})

        result, emit = _run(ActionType.UNEQUIP_RING, actor)

        assert result.success
        assert actor.equipped_ring is None
        assert actor.inventory == [ring]
        assert [e.event_type for e in emit.events] == [EventType.ENTITY_UNEQUIP]
        assert emit.events[0].payload == EquipmentPayload("c1", "Ring of Protection", "ring_1")

    def test_unequip_empty_slot_fails_without_events(self) -> None:
        actor = Character(id="c1", name="Hero", location_id="arena")

        result, emit = _run(ActionType.UNEQUIP_SHIELD, actor)

        assert not result.success
        assert result.error
        assert emit.events == []
