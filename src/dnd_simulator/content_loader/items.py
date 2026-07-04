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
    elif model.type == ItemType.POTION:
        if not model.heal_dice:
            raise RuntimeError(f"Potion '{model.name}' missing required field 'heal_dice'")
        params = {"heal_dice": model.heal_dice}
        if model.equipped:
            params["equipped"] = True
    else:
        # Unknown item types: collect non-standard fields into params
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


#: Creature attribute names for the six equipment slots, in serialization order.
EQUIPMENT_FIELDS = (
    "equipped_weapon",
    "equipped_armor",
    "equipped_shield",
    "equipped_head",
    "equipped_feet",
    "equipped_ring",
)


def serialize_item(item: Item) -> dict[str, Any]:
    """Serialize an Item to a flat dict compatible with ``deserialize_item`` / ``parse_items``."""
    d: dict[str, Any] = {"id": item.id, "name": item.name, "type": item.item_type.value, **item.params}
    if item.weapon_def:
        w = item.weapon_def
        d["weapon_id"] = w.weapon_id
        d["attack_name"] = w.attack_name
        d["category"] = w.category.value
        d["damage"] = [{"dice": dc.dice, "type": dc.type.value} for dc in w.damage]
        d["reach"] = w.reach
        if w.ability:
            d["ability"] = w.ability.value
        d["modifier"] = w.modifier
        d["is_magic"] = w.is_magic
        d["is_finesse"] = w.is_finesse
        if w.grant_conditions:
            d["grant_conditions"] = [c.value for c in w.grant_conditions]
        if w.grant_actions:
            d["grant_actions"] = [a.value for a in w.grant_actions]
    if item.armor_def:
        a = item.armor_def
        d["armor_id"] = a.armor_id
        d["category"] = a.category.value
        d["base_ac"] = a.base_ac
        d["max_dex_bonus"] = a.max_dex_bonus
    if item.shield_def:
        s = item.shield_def
        d["shield_id"] = s.shield_id
        d["ac_bonus"] = s.ac_bonus
    if item.accessory_def:
        acc = item.accessory_def
        d["accessory_id"] = acc.accessory_id
        d["slot"] = acc.slot.value
        if acc.grant_modifiers:
            d["grant_modifiers"] = [
                {"stat": m.stat.value, "op": m.op.value, "value": m.value, "source": m.source}
                for m in acc.grant_modifiers
            ]
    if item.price is not None:
        d["price"] = item.price
    return d


def deserialize_item(data: dict[str, Any]) -> Item:
    """Deserialize an item dict (from ``_serialize_item``) back to a runtime Item with typed defs.

    Unlike bare ``Item()`` construction, this rebuilds WeaponDef / ArmorDef / ShieldDef / AccessoryDef
    from the flat dict, so ``effective_ac`` and weapon attack logic work correctly after save/load.
    """
    from dataclasses import replace

    model = ItemContent.model_validate(data)
    item = _to_item(model, 0)
    saved_id = data.get("id")
    if saved_id:
        return replace(item, id=str(saved_id))
    return item


# Backward compatibility aliases
def parse_equipped_weapon(items: list[Item]) -> Item | None:
    return _parse_equipped(items, ItemType.WEAPON)


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
