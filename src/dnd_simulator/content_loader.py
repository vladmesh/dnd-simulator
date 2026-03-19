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
