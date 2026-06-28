"""The item-transfer primitive shared by trade and loot.

Pure movement of items and gold between two holders. No validation, no pricing,
no consent — the access mode (trade gates on price, loot gates on lootable
state) lives in the caller. This is the single place inventory contents move.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_simulator.core.items import Item
    from dnd_simulator.core.loot import InventoryHolder


def transfer_items(*, src: InventoryHolder, dst: InventoryHolder, items: list[Item], gold: int = 0) -> None:
    """Move `items` and `gold` from `src` to `dst`. Caller guarantees `items` are in `src`."""
    for item in items:
        src.inventory.remove(item)
        dst.inventory.append(item)
    src.gold -= gold
    dst.gold += gold
