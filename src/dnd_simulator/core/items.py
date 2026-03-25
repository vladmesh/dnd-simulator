"""Item model — equipment, consumables, quest objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from dnd_simulator.core.modifiers import Modifier

if TYPE_CHECKING:
    from dnd_simulator.core.action import ActionType
    from dnd_simulator.core.character import Ability, DamageComponent
    from dnd_simulator.core.conditions import Condition


class ItemType(StrEnum):
    """Categories of items."""

    POTION = "potion"
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    ACCESSORY = "accessory"


class EquipmentSlot(StrEnum):
    """Named equipment slots on a creature."""

    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    HEAD = "head"
    FEET = "feet"
    RING = "ring"


class WeaponCategory(StrEnum):
    """D&D 5e weapon categories for proficiency checks."""

    SIMPLE = "simple"
    MARTIAL = "martial"


class ArmorCategory(StrEnum):
    """D&D 5e armor weight classes."""

    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


@dataclass(frozen=True)
class WeaponDef:
    """Typed weapon parameters — replaces raw dict for weapon items.

    ``grant_conditions`` — passive effects active while equipped (permanent).
    ``grant_actions`` — active abilities the weapon provides (e.g. Bless).
    Action cost and handlers are defined in Python, not here.
    """

    weapon_id: str  # mechanical identifier, e.g. "longsword", "rapier"
    attack_name: str  # display name for attack, e.g. "удар мечом"
    category: WeaponCategory
    damage: tuple[DamageComponent, ...]
    reach: int = 5
    ability: Ability | None = None  # None → STR (resolved by get_weapon_attack)
    modifier: int = 0  # magic bonus (+1, +2)
    is_magic: bool = False
    is_finesse: bool = False
    grant_conditions: tuple[Condition, ...] = ()
    grant_actions: tuple[ActionType, ...] = ()


@dataclass(frozen=True)
class ArmorDef:
    """D&D 5e armor definition.

    ``max_dex_bonus`` — cap on DEX modifier added to AC.
    Light armor: 99 (unlimited). Medium: 2. Heavy: 0.
    """

    armor_id: str  # "leather", "chain_mail", "plate"
    category: ArmorCategory
    base_ac: int  # 11 for leather, 16 for chain mail, 18 for plate
    max_dex_bonus: int  # 99 for light, 2 for medium, 0 for heavy
    strength_req: int = 0  # min STR to avoid speed penalty (future)


@dataclass(frozen=True)
class ShieldDef:
    """D&D 5e shield definition."""

    shield_id: str  # "shield", "tower_shield"
    ac_bonus: int = 2


@dataclass(frozen=True)
class AccessoryDef:
    """Accessory definition — head, feet, ring items with stat modifiers."""

    accessory_id: str  # "ring_of_protection", "iron_helmet"
    slot: EquipmentSlot  # which slot this accessory occupies
    grant_modifiers: tuple[Modifier, ...] = ()  # stat modifiers while equipped


@dataclass(frozen=True)
class Item:
    """A single inventory item instance.

    ``params`` carries type-specific data:
    - Potion: ``{"heal_dice": "2d4+2"}``

    Typed defs are set for their respective item types.
    """

    id: str  # unique instance id, e.g. "healing_potion_0"
    name: str  # display name, e.g. "Healing Potion"
    item_type: ItemType
    params: dict[str, object] = field(default_factory=dict)
    weapon_def: WeaponDef | None = None
    armor_def: ArmorDef | None = None
    shield_def: ShieldDef | None = None
    accessory_def: AccessoryDef | None = None
    price: int | None = None
