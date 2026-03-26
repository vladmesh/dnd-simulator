"""Monster and squad parsing from YAML content.

Each parse function: raw YAML dict → Pydantic model_validate → convert to runtime dataclass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_simulator.content_loader.creatures import _to_attacks
from dnd_simulator.content_loader.schemas import (
    EncounterEntryContent,
    MonsterTemplateContent,
    SquadContent,
)
from dnd_simulator.content_loader.utils import _read_yaml, resolve_text
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


def load_monsters(path: Path, lang: str = "en") -> tuple[dict[str, MonsterTemplate], dict[str, list[EncounterEntry]]]:
    """Load monster templates and encounter tables from a world directory.

    Returns (templates_by_id, encounters_by_location_id).
    Missing monsters.yaml → empty dicts (worlds without monsters are valid).
    """
    monsters_data = _read_yaml(path / "monsters.yaml")

    if not monsters_data:
        return {}, {}

    templates_data = monsters_data.get("templates", {})
    templates: dict[str, MonsterTemplate] = {}
    for tid, tdata in templates_data.items():
        templates[str(tid)] = parse_monster_template(str(tid), tdata, lang)

    encounters_data = monsters_data.get("encounters", {})
    encounters = parse_encounters(encounters_data, set(templates.keys())) if encounters_data else {}

    return templates, encounters


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
