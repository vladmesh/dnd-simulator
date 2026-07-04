"""Creature parsing — NPCs and player characters from YAML content.

Each parse function: raw YAML dict → Pydantic model_validate → convert to runtime dataclass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_simulator.content_loader.items import (
    EQUIPMENT_FIELDS,
    deserialize_item,
    extract_all_equipped,
    parse_items,
    serialize_item,
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
from dnd_simulator.core.npc_memory import NpcMemory
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import Npc, resolve_schedule
from dnd_simulator.rules.resources import build_class_resource_pools

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


def parse_class_features(char_class: CharClass, data: dict[str, Any], level: int = 1) -> list[ClassFeatures]:
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
            features.append(FighterFeatures(fighting_style=FightingStyle(style_raw), level=level))
        elif cf_data:
            raise ValueError("Fighter class_features block requires 'fighting_style' key")

    if char_class == CharClass.ROGUE:
        sneak_dice = int(cf_data.get("sneak_attack_dice", 1))
        features.append(RogueFeatures(sneak_attack_dice=sneak_dice, level=level))

    if char_class == CharClass.PALADIN:
        style_raw = cf_data.get("fighting_style")
        style = FightingStyle(style_raw) if style_raw else None
        features.append(PaladinFeatures(fighting_style=style, level=level))

    return features


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
        class_features=parse_class_features(model.char_class, raw_data, level=model.level),
        resource_pools=build_class_resource_pools(model.char_class, level=model.level),
        combat_position=tuple(model.combat_position) if model.combat_position else None,  # type: ignore[arg-type]
        reputation=dict(model.reputation),
        xp_value=model.xp_value,
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
        class_features=parse_class_features(model.char_class, raw_data, level=model.level),
        resource_pools=build_class_resource_pools(model.char_class, level=model.level),
        combat_position=tuple(model.combat_position) if model.combat_position else None,  # type: ignore[arg-type]
        reputation=dict(model.reputation),
        experience=model.experience,
        level_up_available=model.level_up_available,
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


# ---------------------------------------------------------------------------
# Player save/load (kept here so core/player has no content_loader dependency)
# ---------------------------------------------------------------------------


def player_to_full_save_data(player: PlayerCharacter) -> dict[str, Any]:
    """Serialize full player definition for autosave restore."""
    data: dict[str, Any] = {
        "name": player.name,
        "race": player.race.value,
        "class": player.char_class.value,
        "level": player.level,
        "alignment": player.alignment.value,
        "appearance": player.appearance,
        "ability_scores": {a.value: s for a, s in player.ability_scores.scores.items()},
        "hp": player.max_hp,
        "ac": player.ac,
        "gold": player.gold,
        "start_location": player.location_id,
        "current_hp": player.current_hp,
        "experience": player.experience,
        "level_up_available": player.level_up_available,
    }
    # Unified items list: inventory + equipped items. Equipped items get "equipped": true
    # so parse_player can re-equip them.
    all_items: list[dict[str, Any]] = [serialize_item(item) for item in player.inventory]
    for field_name in EQUIPMENT_FIELDS:
        item = getattr(player, field_name)
        if item is not None:
            d = serialize_item(item)
            d["equipped"] = True
            all_items.append(d)
            data[field_name] = d
    if all_items:
        data["items"] = all_items
    # class_features so parse_class_features() can reconstruct them
    cf: dict[str, Any] = {}
    for feat in player.class_features:
        if isinstance(feat, FighterFeatures):
            cf["fighting_style"] = feat.fighting_style.value
        elif isinstance(feat, RogueFeatures):
            cf["sneak_attack_dice"] = feat.sneak_attack_dice
        elif isinstance(feat, PaladinFeatures) and feat.fighting_style is not None:
            cf["fighting_style"] = feat.fighting_style.value
    if cf:
        data["class_features"] = cf
    return data


def load_player_save_data(player: PlayerCharacter, data: dict[str, Any]) -> None:
    """Restore a player's mutable state from a save dict."""
    player.location_id = str(data.get("location_id", data.get("region_id", player.location_id)))
    player.current_hp = int(data.get("current_hp", player.current_hp))
    player.gold = int(data.get("gold", player.gold))
    player.experience = int(data.get("experience", player.experience))
    player.level_up_available = bool(data.get("level_up_available", player.level_up_available))
    items_data = data.get("items")
    if isinstance(items_data, list):
        player.inventory = [deserialize_item(d) for d in items_data]
    for field_name in EQUIPMENT_FIELDS:
        eq_data = data.get(field_name)
        if isinstance(eq_data, dict):
            setattr(player, field_name, deserialize_item(eq_data))
