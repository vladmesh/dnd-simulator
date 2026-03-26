"""Shared utilities for content loading — YAML reading and text resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file, returning empty dict if file doesn't exist."""
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _write_yaml(path: Path, data: dict[str, object]) -> None:
    """Write a dict to a YAML file with unicode support and preserved key order."""
    with path.open("w") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def _load_section(path: Path, section: str) -> dict[str, Any]:
    """Load a section YAML file from a world directory."""
    return _read_yaml(path / f"{section}.yaml")
