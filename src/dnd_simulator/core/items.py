"""Item model — equipment, consumables, quest objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ItemType(StrEnum):
    """Categories of items."""

    POTION = "potion"


@dataclass(frozen=True)
class Item:
    """A single inventory item instance.

    ``params`` carries type-specific data:
    - Potion: ``{"heal_dice": "2d4+2"}``
    """

    id: str  # unique instance id, e.g. "healing_potion_0"
    name: str  # display name, e.g. "Healing Potion"
    item_type: ItemType
    params: dict[str, object] = field(default_factory=dict)
