"""Direct tests for content_loader/refs.py — ID+name pairs behind GM dropdown fields."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dnd_simulator.content_loader.refs import RefType, get_ref_entries
from dnd_simulator.service.game_service import DEFAULT_CONTENT_DIR

WORLD = "test_vale"
WORLD_DIR = DEFAULT_CONTENT_DIR / "worlds" / WORLD


def _yaml(relative: str) -> dict[str, dict[str, object]]:
    with (WORLD_DIR / relative).open() as f:
        data = yaml.safe_load(f) or {}
    assert isinstance(data, dict)
    return data


def _factions(relative: str) -> set[str]:
    return {str(entry["faction"]) for entry in _yaml(relative).values() if entry.get("faction")}


def test_locations_list_every_location_with_its_localised_name() -> None:
    locations = _yaml("geography/locations.yaml")

    en = get_ref_entries(RefType.LOCATIONS, WORLD, DEFAULT_CONTENT_DIR, lang="en")
    ru = get_ref_entries(RefType.LOCATIONS, WORLD, DEFAULT_CONTENT_DIR, lang="ru")

    assert {entry["id"] for entry in en} == set(locations)
    by_id_en = {entry["id"]: entry["name"] for entry in en}
    by_id_ru = {entry["id"]: entry["name"] for entry in ru}
    assert by_id_en["crossroads_tavern"] == "The Dusty Flagon"
    assert by_id_ru["crossroads_tavern"] == "Пыльная Кружка"


@pytest.mark.parametrize(
    ("ref_type", "relative"),
    [
        (RefType.REGIONS, "geography/regions.yaml"),
        (RefType.SETTLEMENTS, "settlements/settlements.yaml"),
        (RefType.NATIONS, "politics/nations.yaml"),
    ],
)
def test_simple_ref_types_list_every_entity_of_their_layer(ref_type: RefType, relative: str) -> None:
    entries = get_ref_entries(ref_type, WORLD, DEFAULT_CONTENT_DIR)
    assert {entry["id"] for entry in entries} == set(_yaml(relative))
    assert all(entry["name"] for entry in entries)


def test_factions_are_the_sorted_union_of_npc_squad_and_monster_factions() -> None:
    expected = _factions("entities/npcs.yaml") | _factions("ecology/squads.yaml") | _monster_template_factions()

    entries = get_ref_entries(RefType.FACTIONS, WORLD, DEFAULT_CONTENT_DIR)

    assert [entry["id"] for entry in entries] == sorted(expected)
    assert all(entry["id"] == entry["name"] for entry in entries)
    assert {"militia", "bandits"} <= expected  # sources from more than one file are merged


def _monster_template_factions() -> set[str]:
    templates = _yaml("ecology/monsters.yaml").get("templates", {})
    assert isinstance(templates, dict)
    return {str(t["faction"]) for t in templates.values() if isinstance(t, dict) and t.get("faction")}


def test_unknown_world_raises(tmp_path: Path) -> None:
    (tmp_path / "worlds").mkdir()
    with pytest.raises(FileNotFoundError, match="nowhere"):
        get_ref_entries(RefType.LOCATIONS, "nowhere", tmp_path)
