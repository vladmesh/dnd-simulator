"""Shared utilities for content loading — YAML reading and text resolution."""

from __future__ import annotations

from pathlib import Path

import yaml


def resolve_text(value: object, lang: str = "en") -> str:
    """Resolve a localizable text field.

    If value is a plain string, return it as-is (backward compat).
    If value is a dict (e.g. {en: "Sword Vale", ru: "Долина Мечей"}),
    pick *lang* with fallback to 'en', then first available.
    """
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or next(iter(value.values()), ""))
    return str(value)


def as_mapping(value: object, where: str) -> dict[str, object]:
    """Narrow a raw YAML value to a string-keyed mapping; raise ValueError naming *where* otherwise."""
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected a mapping, got {type(value).__name__}")
    return {str(key): item for key, item in value.items()}


def as_int(value: object, where: str) -> int:
    """Convert a raw YAML/save scalar with ``int()``; raise ValueError naming *where* for non-scalars."""
    if not isinstance(value, (int, float, str)):
        raise ValueError(f"{where}: expected an integer, got {type(value).__name__}")
    return int(value)


def as_list(value: object, where: str) -> list[object]:
    """Narrow a raw YAML value to a list; raise ValueError naming *where* otherwise."""
    if not isinstance(value, list):
        raise ValueError(f"{where}: expected a list, got {type(value).__name__}")
    return list(value)


def as_mapping_list(value: object, where: str) -> list[dict[str, object]]:
    """Narrow a raw YAML value to a list of string-keyed mappings; raise ValueError naming *where* otherwise."""
    return [as_mapping(item, f"{where}[{index}]") for index, item in enumerate(as_list(value, where))]


def _read_yaml(path: Path) -> dict[str, object]:
    """Read a YAML file, returning empty dict if file doesn't exist or is empty.

    Raises ValueError when the top level of the document is not a mapping.
    """
    if not path.exists():
        return {}
    with path.open() as f:
        return as_mapping(yaml.safe_load(f) or {}, str(path))


def _write_yaml(path: Path, data: dict[str, object]) -> None:
    """Write a dict to a YAML file with unicode support and preserved key order."""
    with path.open("w") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _load_section(path: Path, section: str) -> dict[str, object]:
    """Load a section YAML file from a world directory."""
    return _read_yaml(path / f"{section}.yaml")
