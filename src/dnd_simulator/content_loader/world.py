"""World structure loading — regions, locations, nations, settlements, factions, battle maps."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dnd_simulator.content_loader.utils import _load_section, _read_yaml, resolve_text
from dnd_simulator.core.combat import BattleMap, Wall
from dnd_simulator.core.location import Location, LocationEdge
from dnd_simulator.layers.geography.models import (
    Connection,
    Direction,
    Region,
    TerrainType,
)
from dnd_simulator.layers.politics.models import FactionRelation, Leader, LeaderTrait, Nation
from dnd_simulator.layers.settlements.models import Settlement, SettlementType


def load_world(path: Path, lang: str = "en") -> list[Region]:
    """Load regions from a world directory."""
    regions_data = _load_section(path, "regions")

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
    """Load locations from a world directory.

    Every world must define at least one location explicitly.
    """
    loc_path = path / "locations.yaml"
    locations_data: dict[str, Any] = _read_yaml(loc_path) if loc_path.exists() else {}

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
    """Load nations from a world directory."""
    nations_data = _load_section(path, "nations")

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
    """Load settlements from a world directory.

    Settlements are nested under regions in regions.yaml.
    """
    regions_data = _load_section(path, "regions")

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


def load_world_meta(path: Path, lang: str = "en") -> dict[str, str]:
    """Load world metadata (name, description, default_player_faction) from a world directory."""
    meta = _read_yaml(path / "world.yaml")
    return {
        "name": resolve_text(meta.get("name", path.name), lang),
        "description": resolve_text(meta.get("description", ""), lang),
        "default_player_faction": str(meta.get("default_player_faction", "")),
    }


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
