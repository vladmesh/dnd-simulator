"""World structure loading — regions, locations, nations, settlements, factions, battle maps.

Each load_* function: reads YAML → validates via Pydantic content model → converts to runtime dataclass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_simulator.content_loader.schemas import (
    LocationContent,
    NationContent,
    RegionContent,
    SettlementContent,
)
from dnd_simulator.content_loader.utils import _load_section, _read_yaml, resolve_text
from dnd_simulator.core.combat import BattleMap, Wall
from dnd_simulator.core.location import Location, LocationEdge
from dnd_simulator.layers.geography.models import Connection, Region
from dnd_simulator.layers.politics.models import FactionRelation, Leader, Nation
from dnd_simulator.layers.settlements.models import Settlement

# ---------------------------------------------------------------------------
# Conversion: content model → runtime dataclass
# ---------------------------------------------------------------------------


def _to_region(region_id: str, model: RegionContent, lang: str) -> Region:
    connections = [Connection(target_id=c.target, direction=c.direction) for c in model.connections]
    return Region(
        id=region_id,
        name=resolve_text(model.name, lang),
        latitude=model.latitude,
        longitude=model.longitude,
        elevation=model.elevation,
        terrain=model.terrain,
        water_proximity=model.water_proximity,
        connections=connections,
    )


def _to_location(loc_id: str, model: LocationContent, lang: str) -> Location:
    edges = tuple(LocationEdge(target_id=n.target, distance_m=n.distance) for n in model.neighbors)
    return Location(
        id=loc_id,
        name=resolve_text(model.name, lang),
        region_id=model.region,
        settlement_id=model.settlement,
        edges=edges,
        description=resolve_text(model.description, lang) if model.description else "",
    )


def _to_nation(nation_id: str, model: NationContent, lang: str) -> Nation:
    leader = None
    if model.leader:
        leader = Leader(
            name=resolve_text(model.leader.name, lang),
            age=model.leader.age,
            trait=model.leader.trait,
        )
    return Nation(
        id=nation_id,
        name=resolve_text(model.name, lang),
        regions=list(model.regions),
        wealth=model.wealth,
        military=model.military,
        stability=model.stability,
        leader=leader,
    )


def _to_settlement(settlement_id: str, model: SettlementContent, lang: str) -> Settlement:
    return Settlement(
        id=settlement_id,
        name=resolve_text(model.name, lang),
        region_id=model.region,
        type=model.type,
        population=model.population,
        prosperity=model.prosperity,
        defenses=model.defenses,
    )


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def load_world(path: Path, lang: str = "en") -> list[Region]:
    """Load regions from a world directory."""
    regions_data = _load_section(path, "regions")

    regions: list[Region] = []
    for region_id, rdata in regions_data.items():
        model = RegionContent.model_validate(rdata)
        regions.append(_to_region(str(region_id), model, lang))

    return regions


def load_locations(path: Path, regions: list[Region], lang: str = "en") -> list[Location]:
    """Load locations from a world directory.

    Every world must define at least one location explicitly.
    """
    loc_path = path / "locations.yaml"
    locations_data: dict[str, Any] = _read_yaml(loc_path) if loc_path.exists() else {}

    if not locations_data:
        return []

    return _parse_locations(locations_data, lang)


def _parse_locations(data: dict[str, Any], lang: str = "en") -> list[Location]:
    """Parse locations from YAML data."""
    locations: list[Location] = []
    for loc_id, ldata in data.items():
        model = LocationContent.model_validate(ldata)
        locations.append(_to_location(str(loc_id), model, lang))
    return locations


def load_nations(path: Path, lang: str = "en") -> list[Nation]:
    """Load nations from a world directory."""
    nations_data = _load_section(path, "nations")

    nations: list[Nation] = []
    for nation_id, ndata in nations_data.items():
        model = NationContent.model_validate(ndata)
        nations.append(_to_nation(str(nation_id), model, lang))

    return nations


def load_settlements(path: Path, lang: str = "en") -> list[Settlement]:
    """Load settlements from a layer directory.

    Reads standalone settlements.yaml where each entry has its own ``region`` field.
    """
    settlements_data = _load_section(path, "settlements")

    settlements: list[Settlement] = []
    for settlement_id, sdata in settlements_data.items():
        model = SettlementContent.model_validate(sdata)
        settlements.append(_to_settlement(str(settlement_id), model, lang))

    return settlements


def load_battle_maps(path: Path) -> dict[str, BattleMap]:
    """Load per-region battle map configs (size + walls) from a world directory."""
    regions_data = _load_section(path, "regions")

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


def load_factions(path: Path) -> dict[tuple[str, str], FactionRelation]:
    """Load faction relations from factions.yaml.

    Returns a dict of (faction_a, faction_b) → FactionRelation.
    Keys are canonically sorted (min, max). Missing file → empty dict.
    """
    factions_data = _read_yaml(path / "factions.yaml")

    if not factions_data:
        return {}

    relations: dict[tuple[str, str], FactionRelation] = {}
    for faction_id, fdata in factions_data.items():
        if not isinstance(fdata, dict):
            continue
        for other_id, rel_str in fdata.get("relations", {}).items():
            key = (min(str(faction_id), str(other_id)), max(str(faction_id), str(other_id)))
            relations[key] = FactionRelation(str(rel_str))
    return relations


def extract_region_adjacency(regions: list[Region]) -> dict[str, list[str]]:
    """Build adjacency map from region connections."""
    adjacency: dict[str, list[str]] = {}
    for region in regions:
        adjacency[region.id] = [c.target_id for c in region.connections]
    return adjacency


def extract_region_terrains(regions: list[Region]) -> dict[str, str]:
    """Build terrain map from regions."""
    return {region.id: region.terrain.value for region in regions}
