"""World assembly — create worlds from library templates and fork layers."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from dnd_simulator.content_loader.manifest import LayerSource, LayerType
from dnd_simulator.content_loader.utils import _read_yaml


def assemble_world(
    content_dir: Path,
    world_id: str,
    name: str,
    description: str,
    layer_selections: dict[str, str],
    default_player_faction: str,
) -> Path:
    """Create a new world directory with a manifest pointing to library templates.

    ``layer_selections`` maps layer type name -> template slug.
    All 5 layer types must be present. Each template must exist in the library.

    Returns the path to the created world directory.

    Raises ``RuntimeError`` if a layer type is missing or a template doesn't exist.
    Raises ``FileExistsError`` if the world directory already exists.
    """
    # Validate all layer types present
    for lt in LayerType:
        if lt.value not in layer_selections:
            raise RuntimeError(f"Missing layer type in selections: {lt.value}")

    # Validate all templates exist
    for lt in LayerType:
        template_slug = layer_selections[lt.value]
        template_dir = content_dir / "library" / lt.value / template_slug
        if not template_dir.is_dir():
            raise RuntimeError(
                f"Template '{template_slug}' not found for layer '{lt.value}' (expected at {template_dir})"
            )

    world_path = content_dir / "worlds" / world_id
    if world_path.exists():
        raise FileExistsError(f"World '{world_id}' already exists at {world_path}")

    world_path.mkdir(parents=True)

    manifest = {
        "name": name,
        "description": description,
        "default_player_faction": default_player_faction,
        "layers": {
            lt.value: {
                "source": LayerSource.LIBRARY.value,
                "template": layer_selections[lt.value],
                "version": "1.0",
            }
            for lt in LayerType
        },
    }

    with (world_path / "manifest.yaml").open("w") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return world_path


def fork_layer(content_dir: Path, world_id: str, layer_type: LayerType) -> Path:
    """Copy a library template into a world's custom directory and update the manifest.

    Raises ``FileNotFoundError`` if the world doesn't exist.
    Raises ``ValueError`` if the layer is already custom.
    """
    world_path = content_dir / "worlds" / world_id
    if not world_path.is_dir():
        raise FileNotFoundError(f"World '{world_id}' not found at {world_path}")

    manifest_path = world_path / "manifest.yaml"
    manifest = _read_yaml(manifest_path)

    layer_config = manifest["layers"][layer_type.value]
    if LayerSource(layer_config["source"]) == LayerSource.CUSTOM:
        raise ValueError(f"Layer '{layer_type.value}' is already custom in world '{world_id}'")

    # Resolve source template path
    template_slug = str(layer_config["template"])
    source_dir = content_dir / "library" / layer_type.value / template_slug

    # Copy template files to world's custom directory
    dest_dir = world_path / layer_type.value
    shutil.copytree(source_dir, dest_dir)

    # Update manifest
    manifest["layers"][layer_type.value] = {"source": LayerSource.CUSTOM.value}

    with manifest_path.open("w") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return dest_dir
