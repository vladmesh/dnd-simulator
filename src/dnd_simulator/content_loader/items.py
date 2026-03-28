"""Item and equipment parsing from YAML content.

Each parse function: raw YAML dict → Pydantic model_validate → convert to runtime dataclass.
"""

from __future__ import annotations

from typing import Any

from dnd_simulator.content_loader.schemas import ItemContent
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

# ---------------------------------------------------------------------------
# Conversion: ItemContent → runtime Item
# ---------------------------------------------------------------------------


def _to_weapon_def(model: ItemContent) -> WeaponDef:
    """Build WeaponDef from validated ItemContent."""
    damage = tuple(DamageComponent(dice=d.dice, type=DamageType(d.type)) for d in (model.damage or []))
    ability = Ability(model.ability) if model.ability else None
    grant_conditions = tuple(Condition(c) for c in (model.grant_conditions or []))
    grant_actions = tuple(ActionType(a) for a in (model.grant_actions or []))
    return WeaponDef(
        weapon_id=model.weapon_id or "",
        attack_name=model.attack_name or "",
        category=WeaponCategory(model.category) if model.category else WeaponCategory.SIMPLE,
        damage=damage,
        reach=model.reach or 5,
        ability=ability,
        modifier=model.modifier or 0,
        is_magic=model.is_magic or False,
        is_finesse=model.is_finesse or False,
        is_two_handed=model.is_two_handed or False,
        is_light=model.is_light or False,
        is_heavy=model.is_heavy or False,
        grant_conditions=grant_conditions,
        grant_actions=grant_actions,
    )


def _to_armor_def(model: ItemContent) -> ArmorDef:
    """Build ArmorDef from validated ItemContent."""
    category = ArmorCategory(model.category) if model.category else ArmorCategory.LIGHT
    max_dex: int
    if category == ArmorCategory.LIGHT:
        max_dex = 99
    elif category == ArmorCategory.MEDIUM:
        max_dex = model.max_dex_bonus if model.max_dex_bonus is not None else 2
    else:
        max_dex = model.max_dex_bonus if model.max_dex_bonus is not None else 0
    return ArmorDef(
        armor_id=model.armor_id or "",
        category=category,
        base_ac=model.base_ac or 0,
        max_dex_bonus=max_dex,
        strength_req=model.strength_req or 0,
    )


def _to_shield_def(model: ItemContent) -> ShieldDef:
    """Build ShieldDef from validated ItemContent."""
    return ShieldDef(
        shield_id=model.shield_id or "shield",
        ac_bonus=model.ac_bonus if model.ac_bonus is not None else 2,
    )


def _to_accessory_def(model: ItemContent) -> AccessoryDef:
    """Build AccessoryDef from validated ItemContent."""
    slot = EquipmentSlot(model.slot) if model.slot else EquipmentSlot.RING
    mods_raw = model.modifiers if hasattr(model, "modifiers") and model.modifiers else []
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
        accessory_id=model.accessory_id or "",
        slot=slot,
        grant_modifiers=modifiers,
    )


def _to_item(model: ItemContent, index: int) -> Item:
    """Convert a validated ItemContent to a runtime Item."""
    item_id = f"{model.name.lower().replace(' ', '_')}_{index}"

    weapon_def: WeaponDef | None = None
    armor_def: ArmorDef | None = None
    shield_def: ShieldDef | None = None
    accessory_def: AccessoryDef | None = None
    params: dict[str, object] = {}

    if model.type == ItemType.WEAPON:
        weapon_def = _to_weapon_def(model)
        if model.equipped:
            params["equipped"] = True
    elif model.type == ItemType.ARMOR:
        armor_def = _to_armor_def(model)
        if model.equipped:
            params["equipped"] = True
    elif model.type == ItemType.SHIELD:
        shield_def = _to_shield_def(model)
        if model.equipped:
            params["equipped"] = True
    elif model.type == ItemType.ACCESSORY:
        accessory_def = _to_accessory_def(model)
        if model.equipped:
            params["equipped"] = True
    else:
        # Potion and other types: collect non-standard fields into params
        dumped = model.model_dump(exclude_none=True, exclude={"name", "type", "equipped"})
        params = {k: v for k, v in dumped.items() if v is not None}
        if model.equipped:
            params["equipped"] = True

    return Item(
        id=item_id,
        name=model.name,
        item_type=model.type,
        params=params,
        weapon_def=weapon_def,
        armor_def=armor_def,
        shield_def=shield_def,
        accessory_def=accessory_def,
        price=model.price,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_item_ref(
    idata: dict[str, Any],
    catalog: dict[str, ItemContent],
) -> dict[str, Any]:
    """Resolve an item dict that may contain a ``ref`` key against *catalog*.

    If ``ref`` is present, load the catalog entry and merge any override fields
    (equipped, price, etc.) on top. The ``ref`` key itself is removed from the
    result so downstream validation sees a plain item dict.

    Raises RuntimeError if the ref ID is not found in the catalog.
    """
    ref_id = idata.get("ref")
    if ref_id is None:
        return idata

    if ref_id not in catalog:
        raise RuntimeError(f"Item references unknown catalog entry '{ref_id}'")

    base_dict = catalog[ref_id].model_dump(exclude_none=True)
    overrides = {k: v for k, v in idata.items() if k != "ref"}
    base_dict.update(overrides)
    return base_dict


def parse_items(
    items_data: list[dict[str, Any]],
    *,
    item_catalog: dict[str, ItemContent] | None = None,
) -> list[Item]:
    """Parse item definitions from YAML.

    Each item dict → (optional ref resolution) → ItemContent.model_validate → _to_item → runtime Item.
    IDs are auto-generated as ``<snake_name>_<index>``.

    If *item_catalog* is provided, items with a ``ref`` key are resolved
    against it before validation.
    """
    effective_catalog = item_catalog or {}
    items: list[Item] = []
    for i, idata in enumerate(items_data):
        resolved = resolve_item_ref(idata, effective_catalog)
        model = ItemContent.model_validate(resolved)
        items.append(_to_item(model, i))
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
