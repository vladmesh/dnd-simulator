"""Coverage for rejecting sales of items the seller does not own."""

import pytest
from test_trade import _dagger, _merchant, _player, _potion

from dnd_simulator.rules.trade import validate_sell


@pytest.mark.parametrize("has_other_item", [False, True])
def test_sell_rejects_item_missing_from_seller_inventory(has_other_item: bool) -> None:
    potion = _potion()
    merchant = _merchant(gold=100, items=[potion])
    player = _player(gold=20, items=[_dagger()] if has_other_item else [])
    original_inventory = list(player.inventory)

    error = validate_sell(seller=player, buyer=merchant, item_id=potion.id)

    assert error == "You don't have that item"
    assert player.inventory == original_inventory
    assert merchant.inventory == [potion]
    assert (player.gold, merchant.gold) == (20, 100)
