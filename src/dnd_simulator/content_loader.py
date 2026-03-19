"""Load authored game content from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from dnd_simulator.layers.geography.models import (
    Connection,
    Direction,
    Region,
    TerrainType,
)
from dnd_simulator.layers.politics.models import Leader, LeaderTrait, Nation


def load_world(path: Path) -> list[Region]:
    """Load regions from a world YAML file."""
    with path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)

    regions_data: dict[str, Any] = data["regions"]
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
                name=str(rdata["name"]),
                latitude=float(rdata["latitude"]),
                longitude=float(rdata["longitude"]),
                elevation=float(rdata["elevation"]),
                terrain=TerrainType(rdata["terrain"]),
                water_proximity=float(rdata.get("water_proximity", 0.0)),
                connections=connections,
            )
        )

    return regions


def load_nations(path: Path) -> list[Nation]:
    """Load nations from a world YAML file."""
    with path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)

    nations_data: dict[str, Any] = data.get("nations", {})
    nations: list[Nation] = []

    for nation_id, ndata in nations_data.items():
        leader = None
        leader_data = ndata.get("leader")
        if leader_data:
            leader = Leader(
                name=str(leader_data["name"]),
                age=int(leader_data["age"]),
                trait=LeaderTrait(leader_data["trait"]),
            )

        nations.append(
            Nation(
                id=str(nation_id),
                name=str(ndata["name"]),
                regions=[str(r) for r in ndata.get("regions", [])],
                wealth=float(ndata.get("wealth", 50.0)),
                military=float(ndata.get("military", 50.0)),
                stability=float(ndata.get("stability", 70.0)),
                leader=leader,
            )
        )

    return nations


def extract_region_adjacency(regions: list[Region]) -> dict[str, list[str]]:
    """Build adjacency map from region connections."""
    adjacency: dict[str, list[str]] = {}
    for region in regions:
        adjacency[region.id] = [c.target_id for c in region.connections]
    return adjacency


def extract_region_terrains(regions: list[Region]) -> dict[str, str]:
    """Build terrain map from regions."""
    return {region.id: region.terrain.value for region in regions}
