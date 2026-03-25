"""Load authored game content from YAML files.

Supports two formats:
- Legacy: single YAML file with all sections (regions, nations, npcs, player)
- Directory: folder with separate files (world.yaml, regions.yaml, nations.yaml, npcs.yaml, player.yaml)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Alignment,
    Attack,
    CharClass,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.class_features import ClassFeatures, FighterFeatures, FightingStyle, RogueFeatures
from dnd_simulator.core.combat import BattleMap, Wall
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
from dnd_simulator.core.location import Location, LocationEdge
from dnd_simulator.core.modifiers import Modifier, ModifierOp, StatType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.layers.entities.models import Npc, NpcMemory, resolve_schedule
from dnd_simulator.layers.geography.models import (
    Connection,
    Direction,
    Region,
    TerrainType,
)
from dnd_simulator.layers.politics.models import Leader, LeaderTrait, Nation
from dnd_simulator.layers.settlements.models import Settlement, SettlementType


def resolve_text(value: object, lang: str = "en") -> str:
    """Resolve a localizable text field.

    If value is a plain string, return it as-is (backward compat).
    If value is a dict (e.g. {en: "Sword Vale", ru: "Долина Мечей"}),
    pick *lang* with fallback to 'en', then first available.
    """
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or next(iter(value.values()), ""))
    return str(value)


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file, returning empty dict if file doesn't exist."""
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _resolve_source(path: Path) -> tuple[bool, Path]:
    """Determine if path is a directory or legacy single file.

    Returns (is_directory, resolved_path).
    """
    if path.is_dir():
        return True, path
    return False, path


def _load_section(path: Path, is_dir: bool, section: str) -> dict[str, Any]:
    """Load a section from either directory format or legacy single file."""
    if is_dir:
        return _read_yaml(path / f"{section}.yaml")
    data = _read_yaml(path)
    section_data = data.get(section, {})
    assert isinstance(section_data, dict)
    return section_data


# -- Parsing helpers --


def parse_attacks(attacks_data: list[dict[str, Any]]) -> tuple[Attack, ...]:
    """Parse attack definitions from YAML."""
    attacks: list[Attack] = []
    for adata in attacks_data:
        damage = tuple(
            DamageComponent(dice=str(d["dice"]), type=DamageType(d["type"])) for d in adata.get("damage", [])
        )
        attacks.append(
            Attack(
                name=str(adata["name"]),
                ability=Ability(adata.get("ability", "str")),
                damage=damage,
                reach=int(adata.get("reach", 5)),
            )
        )
    return tuple(attacks)


def parse_ability_scores(data: dict[str, Any], key: str = "ability_scores") -> AbilityScores:
    """Parse ability scores from YAML data."""
    scores = data.get(key)
    if scores:
        return AbilityScores.from_dict(scores)
    return AbilityScores()


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


def parse_class_features(char_class: CharClass, data: dict[str, Any]) -> list[ClassFeatures]:
    """Build class features list from YAML ``class_features`` block + class type.

    Fighter YAML example::

        class_features:
          fighting_style: defense

    Rogue gets RogueFeatures automatically from class; sneak_attack_dice
    can be overridden in YAML (defaults to 1 for level 1).
    """
    cf_data = data.get("class_features") or {}
    features: list[ClassFeatures] = []

    if char_class == CharClass.FIGHTER:
        style_raw = cf_data.get("fighting_style")
        if style_raw:
            features.append(FighterFeatures(fighting_style=FightingStyle(style_raw)))

    if char_class == CharClass.ROGUE:
        sneak_dice = int(cf_data.get("sneak_attack_dice", 1))
        features.append(RogueFeatures(sneak_attack_dice=sneak_dice))

    return features


def build_class_resource_pools(char_class: CharClass) -> list[ResourcePool]:
    """Create default resource pools for a class.

    Fighter: second_wind (1/short rest).
    """
    pools: list[ResourcePool] = []
    if char_class == CharClass.FIGHTER:
        pools.append(ResourcePool(id="second_wind", max_uses=1, current_uses=1, reset_on=RestType.SHORT_REST))
    return pools


# -- Public loaders --


def load_world(path: Path, lang: str = "en") -> list[Region]:
    """Load regions from a world YAML file or directory."""
    is_dir, path = _resolve_source(path)
    regions_data = _load_section(path, is_dir, "regions")

    regions: list[Region] = []
    for region_id, rdata in regions_data.items():
        connections = [
            Connection(
                target_id=str(c["target"]),
                direction=Direction(c["direction"]),
            )
            for c in rdata.get("connections", [])
        ]

        regions.append(
            Region(
                id=str(region_id),
                name=resolve_text(rdata["name"], lang),
                latitude=float(rdata["latitude"]),
                longitude=float(rdata["longitude"]),
                elevation=float(rdata["elevation"]),
                terrain=TerrainType(rdata["terrain"]),
                water_proximity=float(rdata.get("water_proximity", 0.0)),
                connections=connections,
            )
        )

    return regions


def load_locations(path: Path, regions: list[Region], lang: str = "en") -> list[Location]:
    """Load locations from a world YAML file or directory.

    Every world must define at least one location explicitly.
    """
    is_dir, resolved = _resolve_source(path)

    locations_data: dict[str, Any] = {}
    if is_dir:
        loc_path = resolved / "locations.yaml"
        if loc_path.exists():
            locations_data = _read_yaml(loc_path)
    else:
        data = _read_yaml(resolved)
        locations_data = data.get("locations", {})
        assert isinstance(locations_data, dict)

    if not locations_data:
        raise RuntimeError(f"No locations defined in world at {path}. Add a 'locations:' section.")

    return _parse_locations(locations_data, lang)


def _parse_locations(data: dict[str, Any], lang: str = "en") -> list[Location]:
    """Parse locations from YAML data."""
    locations: list[Location] = []
    for loc_id, ldata in data.items():
        edges = tuple(
            LocationEdge(
                target_id=str(n["target"]),
                distance_m=int(n["distance"]),
            )
            for n in ldata.get("neighbors", [])
        )
        locations.append(
            Location(
                id=str(loc_id),
                name=resolve_text(ldata["name"], lang),
                region_id=str(ldata["region"]),
                settlement_id=str(ldata.get("settlement", "")),
                edges=edges,
                description=resolve_text(ldata.get("description", ""), lang),
            )
        )
    return locations


def load_nations(path: Path, lang: str = "en") -> list[Nation]:
    """Load nations from a world YAML file or directory."""
    is_dir, path = _resolve_source(path)
    nations_data = _load_section(path, is_dir, "nations")

    nations: list[Nation] = []
    for nation_id, ndata in nations_data.items():
        leader = None
        leader_data = ndata.get("leader")
        if leader_data:
            leader = Leader(
                name=resolve_text(leader_data["name"], lang),
                age=int(leader_data["age"]),
                trait=LeaderTrait(leader_data["trait"]),
            )

        nations.append(
            Nation(
                id=str(nation_id),
                name=resolve_text(ndata["name"], lang),
                regions=[str(r) for r in ndata.get("regions", [])],
                wealth=float(ndata.get("wealth", 50.0)),
                military=float(ndata.get("military", 50.0)),
                stability=float(ndata.get("stability", 70.0)),
                leader=leader,
            )
        )

    return nations


def load_settlements(path: Path, lang: str = "en") -> list[Settlement]:
    """Load settlements from a world YAML file or directory.

    In directory mode, settlements are nested under regions in regions.yaml.
    """
    is_dir, path = _resolve_source(path)
    regions_data = _load_section(path, is_dir, "regions")

    settlements: list[Settlement] = []
    for region_id, rdata in regions_data.items():
        for sdata in rdata.get("settlements", []):
            settlements.append(
                Settlement(
                    id=str(sdata["id"]),
                    name=resolve_text(sdata["name"], lang),
                    region_id=str(region_id),
                    type=SettlementType(sdata["type"]),
                    population=int(sdata.get("population", 100)),
                    prosperity=float(sdata.get("prosperity", 50.0)),
                    defenses=float(sdata.get("defenses", 30.0)),
                )
            )

    return settlements


def load_npcs(path: Path, lang: str = "en", known_locations: set[str] | None = None) -> list[Npc]:
    """Load NPCs from a world YAML file or directory."""
    is_dir, path = _resolve_source(path)
    npcs_data = _load_section(path, is_dir, "npcs")

    npcs: list[Npc] = []
    for npc_id, ndata in npcs_data.items():
        npcs.append(parse_npc(str(npc_id), ndata, lang=lang, known_locations=known_locations))

    return npcs


def parse_npc(npc_id: str, ndata: dict[str, Any], lang: str = "en", known_locations: set[str] | None = None) -> Npc:
    """Parse a single NPC from YAML data."""
    role = str(ndata.get("role", ""))
    settlement_id = str(ndata.get("settlement_id", ""))

    # Resolve schedule: role-based template with settlement prefix
    schedule = resolve_schedule(role, settlement_id, known_locations=known_locations)

    race = Race(ndata["race"]) if "race" in ndata else Race.HUMAN
    char_class = CharClass(ndata["class"]) if "class" in ndata else CharClass.COMMONER

    attacks = parse_attacks(ndata.get("attacks") or [])
    max_hp = int(ndata.get("hp", 4))
    ai_type = str(ndata.get("ai", "rule_based"))

    # Location: start_location is required (or legacy region_id fallback)
    location_id = str(ndata.get("start_location", "") or ndata.get("region_id", ""))
    if known_locations is not None and location_id and location_id not in known_locations:
        raise RuntimeError(
            f"NPC '{npc_id}' has start_location '{location_id}' which is not a known location. "
            f"Known: {sorted(known_locations)}"
        )

    # Parse initial memory from YAML (optional)
    memory_data = ndata.get("memory")
    memory = NpcMemory.from_dict(memory_data) if isinstance(memory_data, dict) else NpcMemory()

    all_items = parse_items(ndata.get("items") or [])
    equipped, inventory = extract_all_equipped(all_items)

    npc = Npc(
        id=npc_id,
        name=resolve_text(ndata["name"], lang),
        location_id=location_id,
        race=race,
        char_class=char_class,
        role=role,
        personality=resolve_text(ndata.get("personality", ""), lang),
        settlement_id=settlement_id,
        schedule=schedule,
        speed=int(ndata.get("speed", 30)),
        attacks=attacks,
        max_hp=max_hp,
        current_hp=max_hp,
        ac=int(ndata.get("ac", 10)),
        ability_scores=parse_ability_scores(ndata),
        ai_type=ai_type,
        memory=memory,
        inventory=inventory,
        equipped_weapon=equipped["equipped_weapon"],
        equipped_armor=equipped["equipped_armor"],
        equipped_shield=equipped["equipped_shield"],
        equipped_head=equipped["equipped_head"],
        equipped_feet=equipped["equipped_feet"],
        equipped_ring=equipped["equipped_ring"],
        class_features=parse_class_features(char_class, ndata),
        resource_pools=build_class_resource_pools(char_class),
    )
    # Brain is assigned by BrainFactory in GameService, not here.
    return npc


def parse_player(pdata: dict[str, Any]) -> PlayerCharacter:
    """Parse player character from YAML data dict.

    If ``pdata`` does not contain an ``id`` field a unique one is generated
    (``player_<hex8>``).  Callers may supply an explicit ``id`` to preserve
    identity across save/load cycles.
    """
    import uuid

    max_hp = int(pdata.get("hp", 10))
    attacks = parse_attacks(pdata.get("attacks") or [])

    # Support both start_location and legacy start_region
    location_id = str(pdata.get("start_location", pdata.get("start_region", pdata.get("location_id", ""))))

    player_id = str(pdata.get("id", "")) or f"player_{uuid.uuid4().hex[:8]}"

    all_items = parse_items(pdata.get("items") or [])
    equipped, inventory = extract_all_equipped(all_items)

    char_class = CharClass(pdata["class"]) if "class" in pdata else CharClass.FIGHTER

    return PlayerCharacter(
        id=player_id,
        name=str(pdata.get("name", "Adventurer")),
        location_id=location_id,
        race=Race(pdata["race"]) if "race" in pdata else Race.HUMAN,
        char_class=char_class,
        level=int(pdata.get("level", 1)),
        alignment=Alignment(pdata["alignment"]) if "alignment" in pdata else Alignment.TRUE_NEUTRAL,
        appearance=str(pdata.get("appearance", "")),
        ability_scores=parse_ability_scores(pdata),
        max_hp=max_hp,
        current_hp=int(pdata.get("current_hp", max_hp)),
        ac=int(pdata.get("ac", 10)),
        gold=int(pdata.get("gold", 0)),
        attacks=attacks,
        inventory=inventory,
        equipped_weapon=equipped["equipped_weapon"],
        equipped_armor=equipped["equipped_armor"],
        equipped_shield=equipped["equipped_shield"],
        equipped_head=equipped["equipped_head"],
        equipped_feet=equipped["equipped_feet"],
        equipped_ring=equipped["equipped_ring"],
        class_features=parse_class_features(char_class, pdata),
        resource_pools=build_class_resource_pools(char_class),
    )


def load_battle_maps(path: Path) -> dict[str, BattleMap]:
    """Load per-region battle map configs (size + walls) from a world YAML file or directory."""
    is_dir, path = _resolve_source(path)
    regions_data = _load_section(path, is_dir, "regions")

    result: dict[str, BattleMap] = {}
    for region_id, rdata in regions_data.items():
        bm_data = rdata.get("battle_map")
        if not bm_data:
            continue
        walls: list[Wall] = []
        for w in bm_data.get("walls", []):
            walls.append(Wall(x1=int(w[0]), y1=int(w[1]), x2=int(w[2]), y2=int(w[3])))
        result[str(region_id)] = BattleMap(
            width=int(bm_data.get("width", 60)),
            height=int(bm_data.get("height", 60)),
            walls=walls,
        )

    return result


def load_world_meta(path: Path, lang: str = "en") -> dict[str, str]:
    """Load world metadata (name, description) from directory format."""
    is_dir, path = _resolve_source(path)
    if is_dir:
        meta = _read_yaml(path / "world.yaml")
        return {
            "name": resolve_text(meta.get("name", path.name), lang),
            "description": resolve_text(meta.get("description", ""), lang),
        }
    data = _read_yaml(path)
    return {
        "name": resolve_text(data.get("name", path.stem), lang),
        "description": resolve_text(data.get("description", ""), lang),
    }


def extract_region_adjacency(regions: list[Region]) -> dict[str, list[str]]:
    """Build adjacency map from region connections."""
    adjacency: dict[str, list[str]] = {}
    for region in regions:
        adjacency[region.id] = [c.target_id for c in region.connections]
    return adjacency


def extract_region_terrains(regions: list[Region]) -> dict[str, str]:
    """Build terrain map from regions."""
    return {region.id: region.terrain.value for region in regions}
