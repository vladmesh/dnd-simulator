"""Content loader package — re-exports all public (and tested private) functions."""

from dnd_simulator.content_loader.catalogs import load_catalog
from dnd_simulator.content_loader.creatures import (
    load_npcs,
    parse_ability_scores,
    parse_attacks,
    parse_class_features,
    parse_npc,
    parse_player,
)
from dnd_simulator.content_loader.items import (
    deserialize_item,
    extract_all_equipped,
    parse_equipped_weapon,
    parse_items,
)
from dnd_simulator.content_loader.library import (
    TemplateInfo,
    list_compatible_templates,
    list_templates,
)
from dnd_simulator.content_loader.manifest import (
    LayerSource,
    LayerType,
    load_world_meta_from_manifest,
    resolve_manifest,
)
from dnd_simulator.content_loader.monsters import (
    load_monsters,
    load_squads,
    parse_encounters,
    parse_monster_template,
    parse_squad,
    resolve_monster_template,
)
from dnd_simulator.content_loader.utils import _load_section, resolve_text
from dnd_simulator.content_loader.world import (
    extract_region_adjacency,
    extract_region_terrains,
    load_battle_maps,
    load_factions,
    load_location_battle_maps,
    load_locations,
    load_nations,
    load_settlements,
    load_world,
)

__all__ = [
    "LayerSource",
    "LayerType",
    "TemplateInfo",
    "_load_section",
    "deserialize_item",
    "extract_all_equipped",
    "extract_region_adjacency",
    "extract_region_terrains",
    "list_compatible_templates",
    "list_templates",
    "load_battle_maps",
    "load_catalog",
    "load_factions",
    "load_location_battle_maps",
    "load_locations",
    "load_monsters",
    "load_nations",
    "load_npcs",
    "load_settlements",
    "load_squads",
    "load_world",
    "load_world_meta_from_manifest",
    "parse_ability_scores",
    "parse_attacks",
    "parse_class_features",
    "parse_encounters",
    "parse_equipped_weapon",
    "parse_items",
    "parse_monster_template",
    "parse_npc",
    "parse_player",
    "parse_squad",
    "resolve_manifest",
    "resolve_monster_template",
    "resolve_text",
]
