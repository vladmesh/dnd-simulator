"""Save world definitions to YAML directory format.

Inverse of content_loader: takes structured dicts and writes them
to ``content/worlds/{id}/`` as separate YAML files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def save_world(base_dir: Path, world_id: str, data: dict[str, Any], *, overwrite: bool = False) -> Path:
    """Persist a complete world definition to disk.

    Creates ``base_dir/worlds/{world_id}/`` with YAML files for each layer.
    Returns the path to the created directory.

    Raises ``FileExistsError`` if the world directory already exists and
    ``overwrite`` is False.
    """
    worlds_dir = base_dir / "worlds" / world_id
    if worlds_dir.exists() and not overwrite:
        raise FileExistsError(f"World '{world_id}' already exists")

    worlds_dir.mkdir(parents=True, exist_ok=True)

    _write_yaml(
        worlds_dir / "world.yaml",
        {
            "name": data.get("name", world_id),
            "description": data.get("description", ""),
        },
    )

    regions = data.get("regions")
    if regions:
        _write_yaml(worlds_dir / "regions.yaml", regions)

    locations = data.get("locations")
    if locations:
        _write_yaml(worlds_dir / "locations.yaml", locations)

    nations = data.get("nations")
    if nations:
        _write_yaml(worlds_dir / "nations.yaml", nations)

    npcs = data.get("npcs")
    if npcs:
        _write_yaml(worlds_dir / "npcs.yaml", npcs)

    return worlds_dir


def _write_yaml(path: Path, data: object) -> None:
    """Write data to a YAML file."""
    with path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
