"""Container — a lootable world object with no life of its own.

A `Container` is an `Entity` sibling of `Creature`: it holds items and gold but
has no ability scores, HP, turn, or brain. Chests and the lair treasury are
containers. It satisfies the `InventoryHolder` substrate (`core/loot.py`), so the
same `transfer_items` / `take` path that loots a corpse loots a container.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dnd_simulator.core.character import Entity
from dnd_simulator.core.items import Item


@dataclass
class Container(Entity):
    """An inventory-bearing world object. Lootable while `is_open`."""

    inventory: list[Item] = field(default_factory=list)
    gold: int = 0
    is_open: bool = True
