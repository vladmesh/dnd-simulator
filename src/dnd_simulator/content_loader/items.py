"""Item and equipment parsing from YAML content."""

from __future__ import annotations

from typing import Any

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.character import (
    Ability,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.items import (
    AccessoryDef,
    ArmorCategory,
    ArmorDef,
    EquipmentSlot,
    Item,
    ItemType,
    ShieldDef,
    WeaponCategory,
    WeaponDef,
)
from dnd_simulator.core.modifiers import Modifier, ModifierOp, StatType

_WEAPON_KEYS = frozenset(
    {
        "name",
        "type",
        "weapon_id",
        "attack_name",
        "category",
        "damage",
        "reach",
        "ability",
        "modifier",
        "is_magic",
        "is_finesse",
        "grant_conditions",
        "grant_actions",
    }
)


def _parse_weapon_def(idata: dict[str, Any]) -> WeaponDef:
    """Parse WeaponDef from YAML weapon item data."""
    damage = tuple(DamageComponent(dice=str(d["dice"]), type=DamageType(d["type"])) for d in idata["damage"])
    ability_raw = idata.get("ability")
    ability = Ability(ability_raw) if ability_raw else None
    grant_conditions = tuple(Condition(c) for c in idata.get("grant_conditions", []))
    grant_actions = tuple(ActionType(a) for a in idata.get("grant_actions", []))
    return WeaponDef(
        weapon_id=str(idata["weapon_id"]),
        attack_name=str(idata["attack_name"]),
        category=WeaponCategory(idata["category"]),
        damage=damage,
        reach=int(idata.get("reach", 5)),
        ability=ability,
        modifier=int(idata.get("modifier", 0)),
        is_magic=bool(idata.get("is_magic", False)),
        is_finesse=bool(idata.get("is_finesse", False)),
        grant_conditions=grant_conditions,
        grant_actions=grant_actions,
    )


def _parse_armor_def(idata: dict[str, Any]) -> ArmorDef:
    """Parse ArmorDef from YAML armor item data."""
    category = ArmorCategory(idata["category"])
    max_dex: int
    if category == ArmorCategory.LIGHT:
        max_dex = 99
    elif category == ArmorCategory.MEDIUM:
        max_dex = int(idata.get("max_dex_bonus", 2))
    else:
        max_dex = int(idata.get("max_dex_bonus", 0))
    return ArmorDef(
        armor_id=str(idata["armor_id"]),
        category=category,
        base_ac=int(idata["base_ac"]),
        max_dex_bonus=max_dex,
        strength_req=int(idata.get("strength_req", 0)),
    )


def _parse_shield_def(idata: dict[str, Any]) -> ShieldDef:
    """Parse ShieldDef from YAML shield item data."""
    return ShieldDef(
        shield_id=str(idata.get("shield_id", "shield")),
        ac_bonus=int(idata.get("ac_bonus", 2)),
    )


def _parse_accessory_def(idata: dict[str, Any]) -> AccessoryDef:
    """Parse AccessoryDef from YAML accessory item data."""
    slot = EquipmentSlot(idata["slot"])
    mods_raw = idata.get("modifiers") or []
    modifiers = tuple(
        Modifier(
            stat=StatType(m["stat"]),
            op=ModifierOp(m["op"]),
            value=int(m.get("value", 0)),
            source=str(m.get("source", "")),
        )
        for m in mods_raw
    )
    return AccessoryDef(
        accessory_id=str(idata["accessory_id"]),
        slot=slot,
        grant_modifiers=modifiers,
    )


_ARMOR_KEYS = frozenset(
    {"name", "type", "armor_id", "category", "base_ac", "max_dex_bonus", "strength_req", "equipped"}
)
_SHIELD_KEYS = frozenset({"name", "type", "shield_id", "ac_bonus", "equipped"})


def parse_items(items_data: list[dict[str, Any]]) -> list[Item]:
    """Parse item definitions from YAML.

    Each item dict must have ``name`` and ``type``.
    For potions: remaining keys become ``params`` (e.g. ``heal_dice``).
    For weapons/armor/shields: typed defs are built from structured fields.
    IDs are auto-generated as ``<snake_name>_<index>``.
    """
    items: list[Item] = []
    for i, idata in enumerate(items_data):
        name = str(idata["name"])
        item_type = ItemType(idata["type"])
        item_id = f"{name.lower().replace(' ', '_')}_{i}"

        weapon_def: WeaponDef | None = None
        armor_def: ArmorDef | None = None
        shield_def: ShieldDef | None = None
        accessory_def: AccessoryDef | None = None
        params: dict[str, object] = {}

        if item_type == ItemType.WEAPON:
            weapon_def = _parse_weapon_def(idata)
            if idata.get("equipped"):
                params["equipped"] = True
        elif item_type == ItemType.ARMOR:
            armor_def = _parse_armor_def(idata)
            if idata.get("equipped"):
                params["equipped"] = True
        elif item_type == ItemType.SHIELD:
            shield_def = _parse_shield_def(idata)
            if idata.get("equipped"):
                params["equipped"] = True
        elif item_type == ItemType.ACCESSORY:
            accessory_def = _parse_accessory_def(idata)
            if idata.get("equipped"):
                params["equipped"] = True
        else:
            params = {k: v for k, v in idata.items() if k not in ("name", "type")}

        price_raw = idata.get("price")
        price = int(price_raw) if price_raw is not None else None

        items.append(
            Item(
                id=item_id,
                name=name,
                item_type=item_type,
                params=params,
                weapon_def=weapon_def,
                armor_def=armor_def,
                shield_def=shield_def,
                accessory_def=accessory_def,
                price=price,
            )
        )
    return items


def _parse_equipped(items: list[Item], item_type: ItemType, slot: EquipmentSlot | None = None) -> Item | None:
    """Find the first item of given type marked ``equipped: true``.

    For accessories, also matches by slot via ``accessory_def.slot``.
    """
    for item in items:
        if item.item_type != item_type or not item.params.get("equipped"):
            continue
        if (
            item_type == ItemType.ACCESSORY
            and slot is not None
            and (item.accessory_def is None or item.accessory_def.slot != slot)
        ):
            continue
        return item
    return None


# Backward compatibility aliases
def parse_equipped_weapon(items: list[Item]) -> Item | None:
    return _parse_equipped(items, ItemType.WEAPON)


def parse_equipped_armor(items: list[Item]) -> Item | None:
    return _parse_equipped(items, ItemType.ARMOR)


def parse_equipped_shield(items: list[Item]) -> Item | None:
    return _parse_equipped(items, ItemType.SHIELD)


def extract_all_equipped(inventory: list[Item]) -> tuple[dict[str, Item | None], list[Item]]:
    """Extract all equipped items from inventory, returning (equipped_dict, remaining_inventory).

    equipped_dict keys match Creature field names: equipped_weapon, equipped_armor, etc.
    """
    equipped: dict[str, Item | None] = {
        "equipped_weapon": _parse_equipped(inventory, ItemType.WEAPON),
        "equipped_armor": _parse_equipped(inventory, ItemType.ARMOR),
        "equipped_shield": _parse_equipped(inventory, ItemType.SHIELD),
        "equipped_head": _parse_equipped(inventory, ItemType.ACCESSORY, EquipmentSlot.HEAD),
        "equipped_feet": _parse_equipped(inventory, ItemType.ACCESSORY, EquipmentSlot.FEET),
        "equipped_ring": _parse_equipped(inventory, ItemType.ACCESSORY, EquipmentSlot.RING),
    }
    equipped_ids = {item.id for item in equipped.values() if item is not None}
    remaining = [i for i in inventory if i.id not in equipped_ids]
    return equipped, remaining
