"""Load NPC behavior data (schedules, activity flavor) from YAML.

Dialogue stays in models.py for i18n (gettext) support.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from dnd_simulator.core.character import NpcRole
from dnd_simulator.layers.entities.models import NpcActivity

_YAML_PATH = Path(__file__).resolve().parents[4] / "content" / "npc_behaviors.yaml"

# Loaded data — populated by _load() on first access.
_schedule_templates: dict[NpcRole, list[tuple[int, int, NpcActivity, str]]] | None = None
_activity_flavor: dict[tuple[NpcRole, NpcActivity], str] | None = None
_activity_generic: dict[NpcActivity, str] | None = None


def _load() -> None:
    """Parse YAML and populate module-level data. Fails hard if file missing."""
    global _schedule_templates, _activity_flavor, _activity_generic

    if not _YAML_PATH.exists():
        raise RuntimeError(f"NPC behaviors YAML not found: {_YAML_PATH}")

    raw = yaml.safe_load(_YAML_PATH.read_text())

    # Schedules
    _schedule_templates = {}
    for role_str, entries in raw["schedules"].items():
        role = NpcRole(role_str)
        _schedule_templates[role] = [(int(e[0]), int(e[1]), NpcActivity(e[2]), str(e[3])) for e in entries]

    # Activity flavor
    _activity_flavor = {}
    for role_str, activities in raw["activity_flavor"].items():
        role = NpcRole(role_str)
        for activity_str, text in activities.items():
            _activity_flavor[(role, NpcActivity(activity_str))] = str(text)

    # Generic fallbacks
    _activity_generic = {}
    for activity_str, text in raw["activity_flavor_generic"].items():
        _activity_generic[NpcActivity(activity_str)] = str(text)


def get_schedule_templates() -> dict[NpcRole, list[tuple[int, int, NpcActivity, str]]]:
    """Return schedule templates, loading from YAML on first call."""
    if _schedule_templates is None:
        _load()
    assert _schedule_templates is not None
    return _schedule_templates


def get_activity_flavor() -> dict[tuple[NpcRole, NpcActivity], str]:
    """Return activity flavor dict, loading from YAML on first call."""
    if _activity_flavor is None:
        _load()
    assert _activity_flavor is not None
    return _activity_flavor


def get_activity_generic() -> dict[NpcActivity, str]:
    """Return generic activity fallbacks, loading from YAML on first call."""
    if _activity_generic is None:
        _load()
    assert _activity_generic is not None
    return _activity_generic
