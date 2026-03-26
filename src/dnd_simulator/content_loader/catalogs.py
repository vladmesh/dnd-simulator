"""Generic catalog loader — reads a directory of YAML files, validates each against a Pydantic model.

Each .yaml file in the directory is one catalog entry. The filename stem is the catalog ID.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ValidationError

from dnd_simulator.content_loader.utils import _read_yaml


def load_catalog[T: BaseModel](catalog_dir: Path, schema: type[T]) -> dict[str, T]:
    """Load all .yaml files from *catalog_dir*, validate each against *schema*.

    Returns dict keyed by filename stem.
    Raises RuntimeError if the directory doesn't exist or any file fails validation.
    """
    if not catalog_dir.exists():
        raise RuntimeError(f"Catalog directory does not exist: {catalog_dir}")

    result: dict[str, T] = {}
    for yaml_path in sorted(catalog_dir.glob("*.yaml")):
        raw = _read_yaml(yaml_path)
        try:
            result[yaml_path.stem] = schema.model_validate(raw)
        except ValidationError as exc:
            raise RuntimeError(f"Invalid catalog entry {yaml_path.name}: {exc}") from exc
    return result
