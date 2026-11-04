"""Coverage for awareness descriptions of accessories without stat modifiers."""

from dnd_simulator.core.awareness import describe_item
from dnd_simulator.core.items import AccessoryDef, EquipmentSlot, Item, ItemType


def test_describe_accessory_without_modifiers_returns_name() -> None:
    ring = Item(
        id="plain_ring_0",
        name="Plain Ring",
        item_type=ItemType.ACCESSORY,
        accessory_def=AccessoryDef(
            accessory_id="plain_ring",
            slot=EquipmentSlot.RING,
        ),
    )

    assert describe_item(ring) == "Plain Ring"
