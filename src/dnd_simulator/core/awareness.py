"""Structured awareness data passed to Brain.choose_action.

EntitiesLayer builds these from query_fn + internal state, so brains
never touch World directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.items import EquipmentSlot
from dnd_simulator.core.models import EventType

if TYPE_CHECKING:
    from dnd_simulator.core.action import ActionType
    from dnd_simulator.core.items import Item
    from dnd_simulator.core.turn_budget import TurnBudget


@dataclass(frozen=True)
class NearbyEntity:
    """An entity visible to the observer (peaceful context)."""

    id: str
    description: str
    is_wounded: bool = False
    is_hostile: bool = False
    is_dead: bool = False
    name: str = ""
    race: str = ""
    role: str = ""
    faction_id: str = ""
    faction_name: str = ""
    relation: str = ""
    npc_description: str = ""
    is_merchant: bool = False
    lootable: bool = False
    loot_items: list[ItemInfo] = field(default_factory=list)
    loot_gold: int = 0


@dataclass(frozen=True)
class ItemInfo:
    """An inventory item as seen in awareness — lightweight view for brains/UI."""

    id: str
    name: str
    description: str  # e.g. "Healing Potion (heals 2d4+2 HP)"
    item_type: str = ""  # "potion", "weapon", "armor", etc.
    price: int | None = None
    props: dict[str, object] | None = None  # structured properties, see item_props()


@dataclass(frozen=True)
class EquippedInfo:
    """An equipped item as seen in awareness — slot, id, name, description."""

    slot: EquipmentSlot
    item_id: str
    name: str
    description: str
    props: dict[str, object] | None = None


def describe_item(item: Item) -> str:
    """Build a human-readable description of an item for awareness."""
    if item.params.get("heal_dice"):
        return f"{item.name} (heals {item.params['heal_dice']} HP)"
    if item.weapon_def is not None:
        wd = item.weapon_def
        dmg = ", ".join(f"{d.dice} {d.type.value}" for d in wd.damage)
        extras: list[str] = []
        if wd.is_finesse:
            extras.append("finesse")
        if wd.is_magic:
            extras.append("magic")
        if wd.modifier:
            extras.append(f"+{wd.modifier}")
        suffix = f" [{', '.join(extras)}]" if extras else ""
        return f"{item.name} (weapon: {dmg}, reach {wd.reach}ft{suffix})"
    if item.accessory_def is not None:
        ad = item.accessory_def
        from dnd_simulator.core.modifiers import ModifierOp

        parts: list[str] = []
        for m in ad.grant_modifiers:
            sign = "+" if m.op == ModifierOp.ADD and m.value > 0 else ""
            parts.append(f"{sign}{m.value} {m.stat.value.upper()}")
        if parts:
            return f"{item.name} ({', '.join(parts)})"
        return item.name
    return item.name


def item_props(item: Item) -> dict[str, object] | None:
    """Build machine-readable item properties for the UI.

    Values are pure JSON primitives (enums converted to ``.value`` here):
    merchant and loot payloads go through ``dataclasses.asdict`` without a
    blanket JSON pass, so nothing non-primitive may leak in. The frontend
    renders localized labels from these values; ``None`` for items with no
    typed def and no potion effect.
    """
    if item.weapon_def is not None:
        wd = item.weapon_def
        return {
            "kind": "weapon",
            "damage": [{"dice": d.dice, "type": d.type.value} for d in wd.damage],
            "reach": wd.reach,
            "category": wd.category.value,
            "ability": wd.ability.value if wd.ability is not None else None,
            "modifier": wd.modifier,
            "is_magic": wd.is_magic,
            "is_finesse": wd.is_finesse,
            "is_two_handed": wd.is_two_handed,
            "is_light": wd.is_light,
            "is_heavy": wd.is_heavy,
            "conditions": [c.value for c in wd.grant_conditions],
        }
    if item.armor_def is not None:
        ad = item.armor_def
        return {
            "kind": "armor",
            "category": ad.category.value,
            "base_ac": ad.base_ac,
            "max_dex_bonus": ad.max_dex_bonus,
        }
    if item.shield_def is not None:
        return {"kind": "shield", "ac_bonus": item.shield_def.ac_bonus}
    if item.accessory_def is not None:
        acc = item.accessory_def
        return {
            "kind": "accessory",
            "slot": acc.slot.value,
            "modifiers": [{"stat": m.stat.value, "op": m.op.value, "value": m.value} for m in acc.grant_modifiers],
        }
    heal_dice = item.params.get("heal_dice")
    if heal_dice:
        return {"kind": "potion", "heal_dice": heal_dice}
    return None


def item_info(item: Item) -> ItemInfo:
    """Build the standard ItemInfo view of an inventory item."""
    return ItemInfo(
        id=item.id,
        name=item.name,
        description=describe_item(item),
        item_type=str(item.item_type),
        price=item.price,
        props=item_props(item),
    )


@dataclass(frozen=True)
class ResourcePoolInfo:
    """A resource pool as seen in awareness — lightweight view for brains/UI."""

    id: str
    max_uses: int
    current_uses: int


@dataclass(frozen=True)
class CombatEntity:
    """An entity visible in combat — includes distance, direction, and grid position."""

    id: str
    description: str
    is_wounded: bool = False
    is_hostile: bool = False
    distance_ft: int = 0
    direction: str = ""
    x: int = 0
    y: int = 0
    conditions: frozenset[Condition] = field(default_factory=frozenset)


@dataclass(frozen=True)
class MerchantInfo:
    """A nearby merchant's trade info for awareness — what they sell and how much gold they have."""

    id: str
    name: str
    gold: int
    items: list[ItemInfo] = field(default_factory=list)


@dataclass(frozen=True)
class PeacefulAwareness:
    """What a creature knows in peacetime — weather, location, politics, nearby entities."""

    hour: int
    day: int
    month: int
    year: int
    weather: dict[str, object]
    location_name: str
    region_name: str
    settlements: list[dict[str, object]] | None
    territory_owner: str | None
    nation_info: dict[str, object] | None
    nearby: list[NearbyEntity] = field(default_factory=list)
    turn_budget: TurnBudget | None = None
    available_actions: list[ActionType] = field(default_factory=list)
    available_items: list[ItemInfo] = field(default_factory=list)
    equipped: list[EquippedInfo] = field(default_factory=list)
    merchants: list[MerchantInfo] = field(default_factory=list)
    reachable: frozenset[tuple[int, int]] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CombatAwareness:
    """What a creature knows in combat — stats, enemies, terrain."""

    self_hp: int
    self_max_hp: int
    self_ac: int
    self_speed: int
    self_weapon: str
    self_weapon_damage: str
    self_x: int = 0
    self_y: int = 0
    nearby: list[CombatEntity] = field(default_factory=list)
    round_number: int = 1
    walls: list[str] = field(default_factory=list)
    battle_map_ascii: str = ""
    battle_map_width: int = 0
    battle_map_height: int = 0
    battle_map_walls: list[dict[str, int]] = field(default_factory=list)
    turn_budget: TurnBudget | None = None
    self_conditions: frozenset[Condition] = field(default_factory=frozenset)
    available_actions: list[ActionType] = field(default_factory=list)
    available_items: list[ItemInfo] = field(default_factory=list)
    equipped: list[EquippedInfo] = field(default_factory=list)
    reachable: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    is_disengaging: bool = False
    self_resource_pools: tuple[ResourcePoolInfo, ...] = ()


@dataclass(frozen=True)
class PerceivedEvent:
    """A game event as perceived by a specific observer."""

    description: str
    event_type: EventType
    actor_id: str | None = None
    actor_name: str | None = None
    target_id: str | None = None
    data: dict[str, object] = field(default_factory=dict)
