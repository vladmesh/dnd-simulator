"""Pure trade rules — buy/sell validation and execution.

No I/O, no state beyond the objects passed in.
"""

from __future__ import annotations

from dnd_simulator.core.character import Character
from dnd_simulator.core.items import Item
from dnd_simulator.i18n import _
from dnd_simulator.rules.inventory import transfer_items


def _find_item(creature: Character, item_id: str) -> Item | None:
    for item in creature.inventory:
        if item.id == item_id:
            return item
    return None


def validate_buy(*, buyer: Character, seller: Character, item_id: str) -> str | None:
    """Validate a purchase. Returns error message or None if valid."""
    if not seller.is_merchant:
        return _("{name} is not a merchant").format(name=seller.name)
    if buyer.location_id != seller.location_id:
        return _("Must be at the same location as the merchant")
    item = _find_item(seller, item_id)
    if item is None:
        return _("Merchant does not have that item")
    if item.price is None:
        return _("Item has no price and cannot be traded")
    if buyer.gold < item.price:
        return _("Not enough gold (need {price}, have {gold})").format(price=item.price, gold=buyer.gold)
    return None


def validate_sell(*, seller: Character, buyer: Character, item_id: str) -> str | None:
    """Validate a sale. Returns error message or None if valid."""
    if not buyer.is_merchant:
        return _("{name} is not a merchant").format(name=buyer.name)
    if seller.location_id != buyer.location_id:
        return _("Must be at the same location as the merchant")
    item = _find_item(seller, item_id)
    if item is None:
        return _("You don't have that item")
    if item.price is None:
        return _("Item has no price and cannot be traded")
    if buyer.gold < item.price:
        return _("Merchant doesn't have enough gold (need {price}, have {gold})").format(
            price=item.price, gold=buyer.gold
        )
    return None


def execute_buy(*, buyer: Character, seller: Character, item: Item) -> None:
    """Transfer item from seller to buyer, adjust gold. Call after validate_buy."""
    price = item.price
    assert price is not None
    transfer_items(src=seller, dst=buyer, items=[item], gold=-price)


def execute_sell(*, seller: Character, buyer: Character, item: Item) -> None:
    """Transfer item from seller to buyer, adjust gold. Call after validate_sell."""
    price = item.price
    assert price is not None
    transfer_items(src=seller, dst=buyer, items=[item], gold=-price)
