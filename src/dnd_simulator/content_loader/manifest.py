"""Manifest resolution — reads manifest.yaml and resolves layer paths."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from dnd_simulator.content_loader.utils import _read_yaml, resolve_text


class LayerType(StrEnum):
    GEOGRAPHY = "geography"
    POLITICS = "politics"
    SETTLEMENTS = "settlements"
    ECOLOGY = "ecology"
    ENTITIES = "entities"


class LayerSource(StrEnum):
    LIBRARY = "library"
    CUSTOM = "custom"


def resolve_manifest(world_path: Path, content_dir: Path) -> dict[str, Path]:
    """Read manifest.yaml from a world directory and resolve each layer to a concrete path.

    Returns a dict of layer_type (str) -> Path (directory containing layer data files).

    For ``source: library`` layers, resolves to ``content_dir/library/{layer_type}/{template}/``.
    For ``source: custom`` layers, resolves to ``world_path/{layer_type}/``.

    Raises RuntimeError if manifest is missing, a layer is missing, or a resolved path doesn't exist.
    """
    manifest_path = world_path / "manifest.yaml"
    if not manifest_path.exists():
        raise RuntimeError(f"No manifest.yaml found in {world_path}")

    manifest = _read_yaml(manifest_path)
    layers_data = manifest["layers"]

    result: dict[str, Path] = {}
    for layer_type in LayerType:
        lt = layer_type.value
        layer_config = layers_data[lt]
        source = LayerSource(layer_config["source"])

        if source == LayerSource.LIBRARY:
            template = str(layer_config["template"])
            resolved = content_dir / "library" / lt / template
        else:
            resolved = world_path / lt

        if not resolved.is_dir():
            raise RuntimeError(f"Resolved path for layer '{lt}' does not exist: {resolved}")

        result[lt] = resolved

    return result


def load_world_meta_from_manifest(world_path: Path, lang: str = "en") -> dict[str, str]:
    """Load world metadata (name, description, default_player_faction) from manifest.yaml."""
    manifest_path = world_path / "manifest.yaml"
    if not manifest_path.exists():
        raise RuntimeError(f"No manifest.yaml found in {world_path}")

    manifest = _read_yaml(manifest_path)
    return {
        "name": resolve_text(manifest["name"], lang),
        "description": resolve_text(manifest.get("description", ""), lang),
        "default_player_faction": str(manifest.get("default_player_faction", "")),
    }
