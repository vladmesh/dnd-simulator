"""Library catalog — scan template directories and filter by compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dnd_simulator.content_loader.manifest import LayerType
from dnd_simulator.content_loader.utils import _read_yaml


@dataclass(frozen=True)
class TemplateInfo:
    """Metadata for a single library template."""

    slug: str
    name: str
    layer_type: LayerType
    version: str
    description: str
    tags: list[str] = field(default_factory=list)
    requires_geography: list[str] = field(default_factory=list)


def _read_template_info(template_dir: Path, slug: str) -> TemplateInfo:
    """Read metadata.yaml from a template directory and return TemplateInfo."""
    metadata_path = template_dir / "metadata.yaml"
    if not metadata_path.exists():
        raise RuntimeError(f"No metadata.yaml found in {template_dir}")

    data = _read_yaml(metadata_path)
    return TemplateInfo(
        slug=slug,
        name=str(data["name"]),
        layer_type=LayerType(str(data["layer_type"])),
        version=str(data["version"]),
        description=str(data.get("description", "")),
        tags=list(data.get("tags", [])),
        requires_geography=list(data.get("requires_geography", [])),
    )


def list_templates(content_dir: Path, layer_type: LayerType) -> list[TemplateInfo]:
    """List all templates of a given layer type from the library.

    Scans ``content_dir/library/{layer_type}/`` for subdirectories with metadata.yaml.
    Returns results sorted alphabetically by slug.
    """
    library_dir = content_dir / "library" / layer_type.value
    if not library_dir.is_dir():
        return []

    result: list[TemplateInfo] = []
    for entry in sorted(library_dir.iterdir()):
        if entry.is_dir():
            result.append(_read_template_info(entry, entry.name))
    return result


def list_compatible_templates(
    content_dir: Path,
    layer_type: LayerType,
    selected: dict[str, str],
) -> list[TemplateInfo]:
    """List templates compatible with already-selected layers.

    A template is compatible if:
    - It has no ``requires_geography`` (universal), OR
    - Its ``requires_geography`` includes the selected geography slug.

    If no geography is selected yet, all templates are returned.
    """
    all_templates = list_templates(content_dir, layer_type)
    geography_slug = selected.get("geography")

    if not geography_slug:
        return all_templates

    return [t for t in all_templates if not t.requires_geography or geography_slug in t.requires_geography]
