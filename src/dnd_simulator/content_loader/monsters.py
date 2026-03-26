"""Monster and squad parsing from YAML content."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_simulator.content_loader.creatures import parse_ability_scores, parse_attacks
from dnd_simulator.content_loader.utils import _read_yaml, resolve_text
from dnd_simulator.core.monster import EncounterEntry, MonsterTemplate
from dnd_simulator.core.squad import Squad, SquadBehavior, SquadType


def parse_monster_template(template_id: str, data: dict[str, Any], lang: str = "en") -> MonsterTemplate:
    """Parse a single monster template from YAML data."""
    return MonsterTemplate(
        id=template_id,
        name=resolve_text(data["name"], lang),
        hp=int(data["hp"]),
        ac=int(data["ac"]),
        speed=int(data["speed"]),
        ability_scores=parse_ability_scores(data),
        attacks=parse_attacks(data.get("attacks", [])),
        cr=float(data["cr"]),
        faction_id=str(data.get("faction", "")),
    )


def parse_encounters(data: dict[str, Any], known_templates: set[str]) -> dict[str, list[EncounterEntry]]:
    """Parse encounter tables from YAML data.

    Each key is a location_id mapping to a list of encounter entries.
    """
    result: dict[str, list[EncounterEntry]] = {}
    for location_id, entries in data.items():
        parsed: list[EncounterEntry] = []
        for entry in entries:
            template_id = str(entry["template"])
            if template_id not in known_templates:
                raise RuntimeError(f"Encounter at '{location_id}' references unknown monster template '{template_id}'")
            count = entry["count"]
            parsed.append(
                EncounterEntry(
                    template_id=template_id,
                    chance=float(entry["chance"]),
                    count_min=int(count[0]),
                    count_max=int(count[1]),
                )
            )
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
    return Squad(
        id=squad_id,
        name=resolve_text(data["name"], lang),
        faction_id=str(data["faction"]),
        squad_type=SquadType(data["type"]),
        behavior=SquadBehavior(data["behavior"]),
        current_location_id=str(data["start_location"]),
        route=[str(loc) for loc in data.get("route", [])],
        territory=[str(loc) for loc in data.get("territory", [])],
        strength=int(data["strength"]),
        max_strength=int(data.get("max_strength", data["strength"])),
        member_templates=[str(m) for m in data.get("members", [])],
        tick_interval=int(data.get("tick_interval", 3600)),
    )


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
