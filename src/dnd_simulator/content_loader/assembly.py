"""World assembly — create worlds from library templates and fork layers."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from dnd_simulator.content_loader.manifest import LayerSource, LayerType
from dnd_simulator.content_loader.utils import _read_yaml

LAYER_ORDER: list[LayerType] = [
    LayerType.GEOGRAPHY,
    LayerType.POLITICS,
    LayerType.SETTLEMENTS,
    LayerType.ECOLOGY,
    LayerType.ENTITIES,
]


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


def create_empty_world(
    content_dir: Path,
    world_id: str,
    name: str,
    description: str,
    default_player_faction: str,
) -> Path:
    """Create a new world directory with an empty manifest (no layers defined).

    Returns the path to the created world directory.
    Raises ``FileExistsError`` if the world directory already exists.
    """
    world_path = content_dir / "worlds" / world_id
    if world_path.exists():
        raise FileExistsError(f"World '{world_id}' already exists at {world_path}")

    world_path.mkdir(parents=True)

    manifest = {
        "name": name,
        "description": description,
        "default_player_faction": default_player_faction,
        "layers": {},
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


def fork_world(
    content_dir: Path,
    source_world_id: str,
    new_world_id: str,
    from_layer: LayerType | None = None,
) -> Path:
    """Fork a world — copy its manifest with a new ID.

    Library references are preserved (no files copied). Custom layers are copied.
    If ``from_layer`` is specified, that layer and all layers above it in LAYER_ORDER
    are removed from the copy's manifest.

    Raises ``FileNotFoundError`` if the source world doesn't exist.
    Raises ``FileExistsError`` if the new world ID already exists.
    """
    source_path = content_dir / "worlds" / source_world_id
    if not source_path.is_dir():
        raise FileNotFoundError(f"World '{source_world_id}' not found at {source_path}")

    new_path = content_dir / "worlds" / new_world_id
    if new_path.exists():
        raise FileExistsError(f"World '{new_world_id}' already exists at {new_path}")

    source_manifest = _read_yaml(source_path / "manifest.yaml")
    source_layers: dict[str, object] = dict(source_manifest["layers"])

    # Truncate if requested
    if from_layer is not None:
        cut_index = LAYER_ORDER.index(from_layer)
        for lt in LAYER_ORDER[cut_index:]:
            source_layers.pop(lt.value, None)

    new_path.mkdir(parents=True)

    # Copy custom layer directories
    for lt_name, layer_config in source_layers.items():
        assert isinstance(layer_config, dict)
        if LayerSource(layer_config["source"]) == LayerSource.CUSTOM:
            src_dir = source_path / lt_name
            if src_dir.is_dir():
                shutil.copytree(src_dir, new_path / lt_name)

    new_manifest = {
        "name": source_manifest["name"],
        "description": source_manifest.get("description", ""),
        "default_player_faction": source_manifest.get("default_player_faction", ""),
        "layers": source_layers,
    }

    with (new_path / "manifest.yaml").open("w") as f:
        yaml.dump(new_manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return new_path


LAYER_SCAFFOLDS: dict[LayerType, dict[str, str]] = {
    LayerType.GEOGRAPHY: {
        "regions.yaml": "",
        "locations.yaml": "",
    },
    LayerType.POLITICS: {
        "nations.yaml": "",
        "factions.yaml": "",
    },
    LayerType.SETTLEMENTS: {
        "settlements.yaml": "",
    },
    LayerType.ECOLOGY: {
        "squads.yaml": "",
        "monsters.yaml": "templates: {}\nencounters: {}\n",
    },
    LayerType.ENTITIES: {
        "npcs.yaml": "",
    },
}


def scaffold_layer(content_dir: Path, world_id: str, layer_type: LayerType) -> Path:
    """Create a minimal valid custom layer for a world that's missing this layer type.

    Writes scaffold YAML files and updates the manifest to ``source: custom``.

    Raises ``FileNotFoundError`` if the world doesn't exist.
    Raises ``ValueError`` if the layer is already defined in the manifest.
    """
    world_path = content_dir / "worlds" / world_id
    if not world_path.is_dir():
        raise FileNotFoundError(f"World '{world_id}' not found at {world_path}")

    manifest_path = world_path / "manifest.yaml"
    manifest = _read_yaml(manifest_path)

    if layer_type.value in manifest["layers"]:
        raise ValueError(f"Layer '{layer_type.value}' is already defined in world '{world_id}'")

    # Create layer directory with scaffold files
    layer_dir = world_path / layer_type.value
    layer_dir.mkdir(parents=True)

    for filename, content in LAYER_SCAFFOLDS[layer_type].items():
        (layer_dir / filename).write_text(content, encoding="utf-8")

    # Update manifest
    manifest["layers"][layer_type.value] = {"source": LayerSource.CUSTOM.value}

    with manifest_path.open("w") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return layer_dir


def delete_world(content_dir: Path, world_id: str) -> None:
    """Remove a world directory entirely.

    Raises ``FileNotFoundError`` if the world doesn't exist.
    Caller is responsible for safety checks (active sessions, base worlds).
    """
    world_path = content_dir / "worlds" / world_id
    if not world_path.is_dir():
        raise FileNotFoundError(f"World '{world_id}' not found at {world_path}")
    shutil.rmtree(world_path)
