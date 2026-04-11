"""Creature parsing — NPCs and player characters from YAML content.

Each parse function: raw YAML dict → Pydantic model_validate → convert to runtime dataclass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_simulator.content_loader.items import (
    extract_all_equipped,
    parse_items,
)
from dnd_simulator.content_loader.schemas import (
    AttackContent,
    ItemContent,
    NpcContent,
    PlayerContent,
)
from dnd_simulator.content_loader.utils import _load_section, resolve_text
from dnd_simulator.core.character import (
    AbilityScores,
    Attack,
    CharClass,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.class_features import (
    ClassFeatures,
    FighterFeatures,
    FightingStyle,
    PaladinFeatures,
    RogueFeatures,
)
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.layers.entities.models import Npc, NpcMemory, resolve_schedule
from dnd_simulator.rules.resources import build_spell_slot_pools

# ---------------------------------------------------------------------------
# Shared converters
# ---------------------------------------------------------------------------


def _to_attacks(attack_models: list[AttackContent]) -> tuple[Attack, ...]:
    """Convert AttackContent list to runtime Attack tuple."""
    return tuple(
        Attack(
            name=a.name,
            ability=a.ability,
            damage=tuple(DamageComponent(dice=d.dice, type=DamageType(d.type)) for d in a.damage),
            reach=a.reach,
        )
        for a in attack_models
    )


def _to_ability_scores(model: NpcContent | PlayerContent) -> AbilityScores:
    """Convert Pydantic AbilityScoresContent to runtime AbilityScores."""
    return AbilityScores.from_dict(
        {
            "str": model.ability_scores.str_,
            "dex": model.ability_scores.dex,
            "con": model.ability_scores.con,
            "int": model.ability_scores.int_,
            "wis": model.ability_scores.wis,
            "cha": model.ability_scores.cha,
        }
    )


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
        elif cf_data:
            raise ValueError("Fighter class_features block requires 'fighting_style' key")

    if char_class == CharClass.ROGUE:
        sneak_dice = int(cf_data.get("sneak_attack_dice", 1))
        features.append(RogueFeatures(sneak_attack_dice=sneak_dice))

    if char_class == CharClass.PALADIN:
        style_raw = cf_data.get("fighting_style")
        style = FightingStyle(style_raw) if style_raw else None
        features.append(PaladinFeatures(fighting_style=style))

    return features


_SPELL_SLOT_TABLES: dict[CharClass, dict[int, dict[int, int]]] = {
    # Paladin half-caster: spellcasting starts at level 2
    CharClass.PALADIN: {
        2: {1: 2},
        3: {1: 3},
        4: {1: 3},
        5: {1: 4, 2: 2},
    },
}


def build_class_resource_pools(char_class: CharClass, level: int = 1) -> list[ResourcePool]:
    """Create default resource pools for a class at a given level.

    Fighter: second_wind (1/short rest).
    Paladin: lay_on_hands (5 * level, long rest) + spell slots (half-caster table).
    """
    pools: list[ResourcePool] = []
    if char_class == CharClass.FIGHTER:
        pools.append(ResourcePool(id="second_wind", max_uses=1, current_uses=1, reset_on=RestType.SHORT_REST))
    if char_class == CharClass.PALADIN:
        loh_max = 5 * level
        pools.append(
            ResourcePool(id="lay_on_hands", max_uses=loh_max, current_uses=loh_max, reset_on=RestType.LONG_REST)
        )
    if char_class in _SPELL_SLOT_TABLES:
        level_table = _SPELL_SLOT_TABLES[char_class]
        # Find the highest level entry <= creature level
        applicable_levels = [lv for lv in level_table if lv <= level]
        if applicable_levels:
            slot_table = level_table[max(applicable_levels)]
            pools.extend(build_spell_slot_pools(slot_table))
    return pools


# ---------------------------------------------------------------------------
# NPC parsing
# ---------------------------------------------------------------------------


def _to_npc(
    npc_id: str,
    model: NpcContent,
    lang: str,
    known_locations: set[str] | None = None,
    item_catalog: dict[str, ItemContent] | None = None,
) -> Npc:
    """Convert validated NpcContent to runtime Npc."""
    schedule = resolve_schedule(model.role, model.settlement_id, known_locations=known_locations)
    attacks = _to_attacks(model.attacks)

    if known_locations is not None and model.start_location and model.start_location not in known_locations:
        raise RuntimeError(
            f"NPC '{npc_id}' has start_location '{model.start_location}' which is not a known location. "
            f"Known: {sorted(known_locations)}"
        )

    memory = NpcMemory.from_dict(model.memory.model_dump()) if model.memory else NpcMemory()

    all_items = parse_items(
        [item.model_dump(exclude_none=True, exclude_unset=True) for item in model.items],
        item_catalog=item_catalog,
    )
    equipped, inventory = extract_all_equipped(all_items)

    # class_features and resource_pools still use raw dict — they contain logic
    raw_data: dict[str, Any] = {}
    if model.class_features:
        raw_data["class_features"] = model.class_features

    return Npc(
        id=npc_id,
        name=resolve_text(model.name, lang),
        location_id=model.start_location,
        faction_id=model.faction,
        race=model.race,
        char_class=model.char_class,
        level=model.level,
        role=model.role,
        personality=resolve_text(model.personality, lang) if model.personality else "",
        description=resolve_text(model.description, lang) if model.description else "",
        settlement_id=model.settlement_id,
        schedule=schedule,
        speed=model.speed,
        attacks=attacks,
        max_hp=model.hp,
        current_hp=model.hp,
        ac=model.ac,
        ability_scores=_to_ability_scores(model),
        ai_type=model.ai,
        memory=memory,
        gold=model.gold,
        inventory=inventory,
        equipped_weapon=equipped["equipped_weapon"],
        equipped_armor=equipped["equipped_armor"],
        equipped_shield=equipped["equipped_shield"],
        equipped_head=equipped["equipped_head"],
        equipped_feet=equipped["equipped_feet"],
        equipped_ring=equipped["equipped_ring"],
        class_features=parse_class_features(model.char_class, raw_data),
        resource_pools=build_class_resource_pools(model.char_class, level=model.level),
        combat_position=tuple(model.combat_position) if model.combat_position else None,  # type: ignore[arg-type]
        reputation=dict(model.reputation),
    )


def parse_npc(
    npc_id: str,
    ndata: dict[str, Any],
    lang: str = "en",
    known_locations: set[str] | None = None,
    item_catalog: dict[str, ItemContent] | None = None,
) -> Npc:
    """Parse a single NPC from YAML data.

    YAML dict → NpcContent.model_validate → _to_npc → runtime Npc.
    """
    model = NpcContent.model_validate(ndata)
    return _to_npc(npc_id, model, lang, known_locations, item_catalog=item_catalog)


def load_npcs(
    path: Path,
    lang: str = "en",
    known_locations: set[str] | None = None,
    item_catalog: dict[str, ItemContent] | None = None,
) -> list[Npc]:
    """Load NPCs from a world directory."""
    npcs_data = _load_section(path, "npcs")

    npcs: list[Npc] = []
    for npc_id, ndata in npcs_data.items():
        npcs.append(
            parse_npc(str(npc_id), ndata, lang=lang, known_locations=known_locations, item_catalog=item_catalog)
        )

    return npcs


# ---------------------------------------------------------------------------
# Player parsing
# ---------------------------------------------------------------------------


def _to_player(
    model: PlayerContent,
    lang: str,
    item_catalog: dict[str, ItemContent] | None = None,
) -> PlayerCharacter:
    """Convert validated PlayerContent to runtime PlayerCharacter."""
    import uuid

    attacks = _to_attacks(model.attacks)
    all_items = parse_items(
        [item.model_dump(exclude_none=True, exclude_unset=True) for item in model.items],
        item_catalog=item_catalog,
    )
    equipped, inventory = extract_all_equipped(all_items)

    player_id = model.id or f"player_{uuid.uuid4().hex[:8]}"

    # class_features and resource_pools still use raw dict
    raw_data: dict[str, Any] = {}
    if model.class_features:
        raw_data["class_features"] = model.class_features

    return PlayerCharacter(
        id=player_id,
        name=resolve_text(model.name, lang),
        location_id=model.start_location,
        faction_id=model.faction,
        race=model.race,
        char_class=model.char_class,
        level=model.level,
        alignment=model.alignment,
        appearance=resolve_text(model.appearance, lang) if model.appearance else "",
        ability_scores=_to_ability_scores(model),
        max_hp=model.hp,
        current_hp=model.current_hp if model.current_hp is not None else model.hp,
        ac=model.ac,
        gold=model.gold,
        attacks=attacks,
        inventory=inventory,
        equipped_weapon=equipped["equipped_weapon"],
        equipped_armor=equipped["equipped_armor"],
        equipped_shield=equipped["equipped_shield"],
        equipped_head=equipped["equipped_head"],
        equipped_feet=equipped["equipped_feet"],
        equipped_ring=equipped["equipped_ring"],
        class_features=parse_class_features(model.char_class, raw_data),
        resource_pools=build_class_resource_pools(model.char_class, level=model.level),
        combat_position=tuple(model.combat_position) if model.combat_position else None,  # type: ignore[arg-type]
        reputation=dict(model.reputation),
    )


def parse_player(
    pdata: dict[str, Any],
    lang: str = "en",
    item_catalog: dict[str, ItemContent] | None = None,
) -> PlayerCharacter:
    """Parse player character from YAML data dict.

    YAML dict → PlayerContent.model_validate → _to_player → runtime PlayerCharacter.
    If ``pdata`` does not contain an ``id`` field a unique one is generated.
    """
    model = PlayerContent.model_validate(pdata)
    return _to_player(model, lang, item_catalog=item_catalog)


# ---------------------------------------------------------------------------
# Backward-compatible re-exports (used by other modules)
# ---------------------------------------------------------------------------


def parse_attacks(attacks_data: list[dict[str, Any]]) -> tuple[Attack, ...]:
    """Parse attack definitions from YAML — validates via AttackContent."""
    models = [AttackContent.model_validate(a) for a in attacks_data]
    return _to_attacks(models)


def parse_ability_scores(data: dict[str, Any], key: str = "ability_scores") -> AbilityScores:
    """Parse ability scores from YAML data — validates via AbilityScoresContent."""
    from dnd_simulator.content_loader.schemas import AbilityScoresContent

    scores = data.get(key)
    if scores:
        model = AbilityScoresContent.model_validate(scores)
        return AbilityScores.from_dict(
            {
                "str": model.str_,
                "dex": model.dex,
                "con": model.con,
                "int": model.int_,
                "wis": model.wis,
                "cha": model.cha,
            }
        )
    return AbilityScores()
