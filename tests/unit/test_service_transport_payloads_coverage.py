"""Coverage for dataclass serialization and accessory inventory slots."""

from __future__ import annotations

import json

import pytest

from dnd_simulator.core.character import AbilityScores, Alignment, CharClass, Race
from dnd_simulator.core.items import AccessoryDef, EquipmentSlot, Item, ItemType
from dnd_simulator.core.modifiers import Modifier, ModifierOp, StatType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.reactions import ReactionTrigger, TriggerType
from dnd_simulator.service.transport_payloads import _json_safe, build_inventory_payload


def test_json_safe_serializes_dataclass_fields_recursively() -> None:
    trigger = ReactionTrigger(
        trigger_type=TriggerType.LEAVING_REACH,
        source_creature_id="goblin_1",
        data={"from": (0, 0), "to": (1, 0)},
    )

    payload = _json_safe(trigger)

    assert payload == {
        "trigger_type": "leaving_reach",
        "source_creature_id": "goblin_1",
        "data": {"from": [0, 0], "to": [1, 0]},
    }
    assert json.loads(json.dumps(payload)) == payload
    assert trigger.data == {"from": (0, 0), "to": (1, 0)}


@pytest.mark.parametrize("slot", [EquipmentSlot.HEAD, EquipmentSlot.FEET, EquipmentSlot.RING])
def test_inventory_payload_includes_accessory_slot(slot: EquipmentSlot) -> None:
    accessory = Item(
        id="charm_0",
        name="Protective Charm",
        item_type=ItemType.ACCESSORY,
        accessory_def=AccessoryDef(
            accessory_id="protective_charm",
            slot=slot,
            grant_modifiers=(Modifier(stat=StatType.AC, op=ModifierOp.ADD, value=1, source="protective_charm"),),
        ),
        price=100,
    )
    potion = Item(
        id="potion_0",
        name="Healing Potion",
        item_type=ItemType.POTION,
        params={"heal_dice": "2d4+2"},
        price=50,
    )
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
        inventory=[accessory, potion],
    )

    payload = build_inventory_payload(player)

    assert payload == [
        {
            "id": "charm_0",
            "name": "Protective Charm",
            "type": "accessory",
            "description": "Protective Charm (+1 AC)",
            "price": 100,
            "props": {
                "kind": "accessory",
                "slot": slot.value,
                "modifiers": [{"stat": "ac", "op": "add", "value": 1}],
            },
            "slot": slot.value,
        },
        {
            "id": "potion_0",
            "name": "Healing Potion",
            "type": "potion",
            "description": "Healing Potion (heals 2d4+2 HP)",
            "price": 50,
            "props": {"kind": "potion", "heal_dice": "2d4+2"},
        },
    ]
    assert json.loads(json.dumps(payload)) == payload
