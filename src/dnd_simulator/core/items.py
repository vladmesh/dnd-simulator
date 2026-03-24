"""Item model — equipment, consumables, quest objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_simulator.core.action import ActionType
    from dnd_simulator.core.character import Ability, DamageComponent
    from dnd_simulator.core.conditions import Condition


class ItemType(StrEnum):
    """Categories of items."""

    POTION = "potion"
    WEAPON = "weapon"


@dataclass(frozen=True)
class WeaponDef:
    """Typed weapon parameters — replaces raw dict for weapon items.

    ``grant_conditions`` — passive effects active while equipped (permanent).
    ``grant_actions`` — active abilities the weapon provides (e.g. Bless).
    Action cost and handlers are defined in Python, not here.
    """

    attack_name: str  # replaces default attack name, e.g. "удар мечом"
    damage: tuple[DamageComponent, ...]
    reach: int = 5
    ability: Ability | None = None  # None → STR (resolved by get_weapon_attack)
    modifier: int = 0  # magic bonus (+1, +2)
    is_magic: bool = False
    is_finesse: bool = False
    grant_conditions: tuple[Condition, ...] = ()
    grant_actions: tuple[ActionType, ...] = ()


@dataclass(frozen=True)
class Item:
    """A single inventory item instance.

    ``params`` carries type-specific data:
    - Potion: ``{"heal_dice": "2d4+2"}``

    ``weapon_def`` is set only for WEAPON items.
    """

    id: str  # unique instance id, e.g. "healing_potion_0"
    name: str  # display name, e.g. "Healing Potion"
    item_type: ItemType
    params: dict[str, object] = field(default_factory=dict)
    weapon_def: WeaponDef | None = None
