"""Equipment registry pins (phase 3 task 6, variant A).

`Creature.equipped` is a dict[EquipmentSlot, Item]; the six `equipped_*` names are compat
properties over it. Handlers are factory-built per slot; the 12 equip/unequip ActionTypes and
their wire contract stay intact (the 12→2 collapse is deferred — see sprint Deferred).
"""

from __future__ import annotations

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.action_defs import ACTION_DEFS
from dnd_simulator.core.character import Creature
from dnd_simulator.core.items import EquipmentSlot, Item, ItemType
from dnd_simulator.rules.handlers.equipment import EQUIPMENT_HANDLERS

_ALL_EQUIP_ACTIONS = [
    ActionType.EQUIP,
    ActionType.UNEQUIP,
    ActionType.EQUIP_ARMOR,
    ActionType.UNEQUIP_ARMOR,
    ActionType.EQUIP_SHIELD,
    ActionType.UNEQUIP_SHIELD,
    ActionType.EQUIP_HEAD,
    ActionType.UNEQUIP_HEAD,
    ActionType.EQUIP_FEET,
    ActionType.UNEQUIP_FEET,
    ActionType.EQUIP_RING,
    ActionType.UNEQUIP_RING,
]


def _sword() -> Item:
    return Item(id="sword_0", name="Sword", item_type=ItemType.WEAPON)


class TestCompatProperties:
    def test_property_reads_from_dict(self) -> None:
        sword = _sword()
        c = Creature(id="c", name="C", location_id="loc", equipped={EquipmentSlot.WEAPON: sword})
        assert c.equipped_weapon is sword

    def test_property_write_updates_dict(self) -> None:
        c = Creature(id="c", name="C", location_id="loc")
        sword = _sword()
        c.equipped_weapon = sword
        assert c.equipped[EquipmentSlot.WEAPON] is sword
        assert c.equipped_weapon is sword

    def test_setting_none_clears_slot(self) -> None:
        c = Creature(id="c", name="C", location_id="loc", equipped={EquipmentSlot.WEAPON: _sword()})
        c.equipped_weapon = None
        assert EquipmentSlot.WEAPON not in c.equipped
        assert c.equipped_weapon is None

    def test_empty_slots_read_none(self) -> None:
        c = Creature(id="c", name="C", location_id="loc")
        assert c.equipped_armor is None
        assert c.equipped_shield is None
        assert c.equipped_ring is None


class TestActionContractIntact:
    def test_all_twelve_action_defs_present(self) -> None:
        for at in _ALL_EQUIP_ACTIONS:
            assert at in ACTION_DEFS, f"{at} missing from ACTION_DEFS"

    def test_factory_registry_covers_all_twelve(self) -> None:
        assert set(EQUIPMENT_HANDLERS) == set(_ALL_EQUIP_ACTIONS)

    def test_weapon_slot_keeps_special_flags(self) -> None:
        # The weapon slot is the only one that ends a peaceful turn and carries an llm_hint.
        assert ACTION_DEFS[ActionType.EQUIP].ends_peaceful_turn is True
        assert ACTION_DEFS[ActionType.EQUIP].llm_hint != ""
        assert ACTION_DEFS[ActionType.EQUIP_ARMOR].ends_peaceful_turn is False
        assert ACTION_DEFS[ActionType.EQUIP_ARMOR].llm_hint == ""
