"""Creature parsing — NPCs and player characters from YAML content."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_simulator.content_loader.items import (
    extract_all_equipped,
    parse_items,
)
from dnd_simulator.content_loader.utils import _load_section, resolve_text
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Alignment,
    Attack,
    CharClass,
    DamageComponent,
    DamageType,
    NpcRole,
    Race,
)
from dnd_simulator.core.class_features import ClassFeatures, FighterFeatures, FightingStyle, RogueFeatures
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.layers.entities.models import Npc, NpcMemory, resolve_schedule


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


def load_npcs(path: Path, lang: str = "en", known_locations: set[str] | None = None) -> list[Npc]:
    """Load NPCs from a world directory."""
    npcs_data = _load_section(path, "npcs")

    npcs: list[Npc] = []
    for npc_id, ndata in npcs_data.items():
        npcs.append(parse_npc(str(npc_id), ndata, lang=lang, known_locations=known_locations))

    return npcs


def parse_npc(npc_id: str, ndata: dict[str, Any], lang: str = "en", known_locations: set[str] | None = None) -> Npc:
    """Parse a single NPC from YAML data."""
    role_str = str(ndata.get("role", ""))
    role = NpcRole(role_str) if role_str else NpcRole.COMMONER
    settlement_id = str(ndata.get("settlement_id", ""))

    # Resolve schedule: role-based template with settlement prefix
    schedule = resolve_schedule(role, settlement_id, known_locations=known_locations)

    race = Race(ndata["race"]) if "race" in ndata else Race.HUMAN
    char_class = CharClass(ndata["class"]) if "class" in ndata else CharClass.COMMONER

    attacks = parse_attacks(ndata.get("attacks") or [])
    max_hp = int(ndata.get("hp", 4))
    ai_type = str(ndata.get("ai", "rule_based"))

    location_id = str(ndata.get("start_location", ""))
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
        faction_id=str(ndata.get("faction", "")),
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
        gold=int(ndata.get("gold", 0)),
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

    location_id = str(pdata.get("start_location", ""))

    player_id = str(pdata.get("id", "")) or f"player_{uuid.uuid4().hex[:8]}"

    all_items = parse_items(pdata.get("items") or [])
    equipped, inventory = extract_all_equipped(all_items)

    char_class = CharClass(pdata["class"]) if "class" in pdata else CharClass.FIGHTER

    return PlayerCharacter(
        id=player_id,
        name=str(pdata.get("name", "Adventurer")),
        location_id=location_id,
        faction_id=str(pdata.get("faction", "")),
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
