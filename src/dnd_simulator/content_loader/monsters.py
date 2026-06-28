"""Monster and squad parsing from YAML content.

Each parse function: raw YAML dict → Pydantic model_validate → convert to runtime dataclass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_simulator.content_loader.creatures import _to_attacks
from dnd_simulator.content_loader.items import parse_items
from dnd_simulator.content_loader.schemas import (
    EncounterEntryContent,
    ItemContent,
    LairContent,
    MonsterTemplateContent,
    SquadContent,
)
from dnd_simulator.content_loader.utils import _read_yaml, resolve_text
from dnd_simulator.core.lair import Lair
from dnd_simulator.core.monster import EncounterEntry, MonsterTemplate
from dnd_simulator.core.squad import Squad

# ---------------------------------------------------------------------------
# Conversion: content model → runtime dataclass
# ---------------------------------------------------------------------------


def _to_monster_template(template_id: str, model: MonsterTemplateContent, lang: str) -> MonsterTemplate:
    """Convert validated MonsterTemplateContent to runtime MonsterTemplate."""
    from dnd_simulator.core.character import AbilityScores

    attacks = _to_attacks(model.attacks)
    ability_scores = AbilityScores.from_dict(
        {
            "str": model.ability_scores.str_,
            "dex": model.ability_scores.dex,
            "con": model.ability_scores.con,
            "int": model.ability_scores.int_,
            "wis": model.ability_scores.wis,
            "cha": model.ability_scores.cha,
        }
    )
    return MonsterTemplate(
        id=template_id,
        name=resolve_text(model.name, lang),
        hp=model.hp,
        ac=model.ac,
        speed=model.speed,
        ability_scores=ability_scores,
        attacks=attacks,
        cr=model.cr,
        faction_id=model.faction,
        description=resolve_text(model.description, lang) if model.description else "",
    )


def _to_encounter_entry(model: EncounterEntryContent) -> EncounterEntry:
    """Convert validated EncounterEntryContent to runtime EncounterEntry."""
    return EncounterEntry(
        template_id=model.template,
        chance=model.chance,
        count_min=model.count[0],
        count_max=model.count[1],
    )


def _to_squad(squad_id: str, model: SquadContent, lang: str) -> Squad:
    """Convert validated SquadContent to runtime Squad."""
    return Squad(
        id=squad_id,
        name=resolve_text(model.name, lang),
        faction_id=model.faction,
        squad_type=model.type,
        behavior=model.behavior,
        current_location_id=model.start_location,
        route=list(model.route),
        territory=list(model.territory),
        strength=model.strength,
        max_strength=model.max_strength if model.max_strength is not None else model.strength,
        member_templates=list(model.members),
        tick_interval=model.tick_interval,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_monster_template(template_id: str, data: dict[str, Any], lang: str = "en") -> MonsterTemplate:
    """Parse a single monster template from YAML data."""
    model = MonsterTemplateContent.model_validate(data)
    return _to_monster_template(template_id, model, lang)


def resolve_monster_template(
    template_id: str,
    data: dict[str, Any],
    catalog: dict[str, MonsterTemplateContent],
    lang: str = "en",
) -> MonsterTemplate:
    """Resolve a monster template entry that may reference a catalog via 'base'.

    If *data* contains a 'base' key, load the catalog entry and merge any
    override fields on top. Otherwise parse as a full inline template.
    Raises RuntimeError if the base ID is not found in the catalog.
    """
    base_id = data.get("base")
    if base_id is None:
        # Inline template — parse as before
        return parse_monster_template(template_id, data, lang)

    if base_id not in catalog:
        raise RuntimeError(f"Monster template '{template_id}' references unknown catalog entry '{base_id}'")

    # Start from catalog entry, apply overrides
    base_dict = catalog[base_id].model_dump(by_alias=True)
    overrides = {k: v for k, v in data.items() if k != "base"}
    base_dict.update(overrides)

    model = MonsterTemplateContent.model_validate(base_dict)
    return _to_monster_template(template_id, model, lang)


def parse_encounters(data: dict[str, Any], known_templates: set[str]) -> dict[str, list[EncounterEntry]]:
    """Parse encounter tables from YAML data.

    Each key is a location_id mapping to a list of encounter entries.
    """
    result: dict[str, list[EncounterEntry]] = {}
    for location_id, entries in data.items():
        parsed: list[EncounterEntry] = []
        for entry in entries:
            model = EncounterEntryContent.model_validate(entry)
            if model.template not in known_templates:
                raise RuntimeError(
                    f"Encounter at '{location_id}' references unknown monster template '{model.template}'"
                )
            parsed.append(_to_encounter_entry(model))
        result[location_id] = parsed
    return result


def load_monsters(
    path: Path,
    lang: str = "en",
    catalog: dict[str, MonsterTemplateContent] | None = None,
) -> tuple[dict[str, MonsterTemplate], dict[str, list[EncounterEntry]]]:
    """Load monster templates and encounter tables from a world directory.

    If *catalog* is provided, templates with a ``base`` key resolve against it.
    Returns (templates_by_id, encounters_by_location_id).
    Missing monsters.yaml → empty dicts (worlds without monsters are valid).
    """
    monsters_data = _read_yaml(path / "monsters.yaml")

    if not monsters_data:
        return {}, {}

    templates_data = monsters_data.get("templates", {})
    templates: dict[str, MonsterTemplate] = {}
    effective_catalog = catalog or {}
    for tid, tdata in templates_data.items():
        templates[str(tid)] = resolve_monster_template(str(tid), tdata, effective_catalog, lang)

    encounters_data = monsters_data.get("encounters", {})
    encounters = parse_encounters(encounters_data, set(templates.keys())) if encounters_data else {}

    return templates, encounters


def _to_lair(
    lair_id: str,
    model: LairContent,
    lang: str,
    item_catalog: dict[str, ItemContent] | None = None,
) -> Lair:
    """Convert validated LairContent to runtime Lair, resolving any treasure item refs."""
    treasure_items: list[Any] = []
    treasure_gold = 0
    treasure_behind_core = True
    if model.treasure is not None:
        treasure_items = parse_items(
            [item.model_dump(exclude_none=True, exclude_unset=True) for item in model.treasure.items],
            item_catalog=item_catalog,
        )
        treasure_gold = model.treasure.gold
        treasure_behind_core = model.treasure.behind_core
    return Lair(
        id=lair_id,
        name=resolve_text(model.name, lang),
        faction_id=model.faction,
        location_id=model.location,
        members=list(model.members),
        core=model.core,
        respawn_interval=model.respawn_interval,
        depletion_chance=model.depletion_chance,
        treasure_items=treasure_items,
        treasure_gold=treasure_gold,
        treasure_behind_core=treasure_behind_core,
    )


def parse_lairs(
    data: dict[str, Any],
    known_templates: set[str],
    lang: str = "en",
    item_catalog: dict[str, ItemContent] | None = None,
) -> dict[str, Lair]:
    """Parse lairs from YAML data, validating that every template ref exists.

    Each key is a lair_id. Unknown ``core``/``members`` refs raise RuntimeError (fail-fast);
    unknown treasure item refs raise RuntimeError via the catalog resolver.
    """
    result: dict[str, Lair] = {}
    for lair_id, ldata in data.items():
        model = LairContent.model_validate(ldata)
        refs = [*model.members, *([model.core] if model.core else [])]
        for ref in refs:
            if ref not in known_templates:
                raise RuntimeError(f"Lair '{lair_id}' references unknown monster template '{ref}'")
        result[str(lair_id)] = _to_lair(str(lair_id), model, lang, item_catalog=item_catalog)
    return result


def load_lairs(
    path: Path,
    known_templates: set[str],
    lang: str = "en",
    item_catalog: dict[str, ItemContent] | None = None,
) -> dict[str, Lair]:
    """Load lairs from a world directory's ``lairs.yaml``.

    Returns lairs_by_id. Missing lairs.yaml -> empty dict.
    """
    lairs_data = _read_yaml(path / "lairs.yaml")
    if not lairs_data:
        return {}
    return parse_lairs(lairs_data, known_templates, lang, item_catalog=item_catalog)


def parse_squad(squad_id: str, data: dict[str, Any], lang: str = "en") -> Squad:
    """Parse a single squad from YAML data."""
    model = SquadContent.model_validate(data)
    return _to_squad(squad_id, model, lang)


def load_squads(path: Path, lang: str = "en") -> dict[str, Squad]:
    """Load squads from a world directory.

    Returns squads_by_id. Missing squads.yaml -> empty dict.
    """
    squads_data = _read_yaml(path / "squads.yaml")

    if not squads_data:
        return {}

    squads: dict[str, Squad] = {}
    for sid, sdata in squads_data.items():
        squads[str(sid)] = parse_squad(str(sid), sdata, lang)
    return squads
