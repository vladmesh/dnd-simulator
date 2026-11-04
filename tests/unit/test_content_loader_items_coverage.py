"""Coverage for item conversion, serialization, and validation edge cases."""

import pytest

from dnd_simulator.content_loader.items import deserialize_item, parse_items, serialize_item
from dnd_simulator.core.action import ActionType
from dnd_simulator.core.items import Item, ItemType


@pytest.mark.parametrize("heal_dice", [None, ""])
def test_potion_requires_nonempty_heal_dice(heal_dice: str | None) -> None:
    with pytest.raises(RuntimeError, match="Potion 'Health Potion' missing required field 'heal_dice'"):
        parse_items([{"name": "Health Potion", "type": "potion", "heal_dice": heal_dice}])


@pytest.mark.parametrize("equipped", [False, True])
def test_parse_potion_preserves_healing_and_equipped_flag(equipped: bool) -> None:
    items = parse_items([{"name": "Health Potion", "type": "potion", "heal_dice": "2d4+2", "equipped": equipped}])

    expected_params: dict[str, object] = {"heal_dice": "2d4+2"}
    if equipped:
        expected_params["equipped"] = True
    assert items == [
        Item(id="health_potion_0", name="Health Potion", item_type=ItemType.POTION, params=expected_params)
    ]


def test_weapon_granted_actions_survive_serialization_round_trip() -> None:
    item = parse_items(
        [
            {
                "name": "Blessed Dagger",
                "type": "weapon",
                "weapon_id": "blessed_dagger",
                "category": "simple",
                "attack_name": "dagger strike",
                "damage": [{"dice": "1d4", "type": "piercing"}],
                "ability": "dex",
                "is_finesse": True,
                "grant_actions": ["bless", "dodge"],
            }
        ]
    )[0]
    assert item.weapon_def is not None
    assert item.weapon_def.grant_actions == (ActionType.BLESS, ActionType.DODGE)

    serialized = serialize_item(item)

    assert serialized["grant_actions"] == ["bless", "dodge"]
    assert deserialize_item(serialized) == item


@pytest.mark.parametrize("saved_id", [None, ""])
def test_deserialize_without_saved_id_generates_id(saved_id: str | None) -> None:
    data: dict[str, object] = {
        "name": "Health Potion",
        "type": "potion",
        "heal_dice": "2d4+2",
        "price": 50,
    }
    if saved_id is not None:
        data["id"] = saved_id

    item = deserialize_item(data)

    assert item == Item(
        id="health_potion_0",
        name="Health Potion",
        item_type=ItemType.POTION,
        params={"heal_dice": "2d4+2"},
        price=50,
    )
