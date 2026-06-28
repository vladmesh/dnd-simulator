"""The lootable substrate: a uniform inventory/gold holder.

`InventoryHolder` is the structural interface shared by everything that can
hold and exchange items — creatures (corpses), characters, and containers.
Trade, looting, and (later) theft are different access modes over this one
substrate; the transfer primitive in `rules/inventory.py` operates on it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from dnd_simulator.core.items import Item


@runtime_checkable
class InventoryHolder(Protocol):
    """Anything with an item bag and a gold purse.

    Satisfied structurally by `Creature` (and its `Character` subclasses) and by
    `Container`. No behavior — just the two fields the transfer primitive moves.
    """

    inventory: list[Item]
    gold: int
