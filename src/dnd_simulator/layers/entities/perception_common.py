"""Shared helpers for subjective entity-event descriptions."""

from __future__ import annotations

from collections.abc import Callable

from dnd_simulator.core.character import Character, Entity
from dnd_simulator.i18n import _

GetEntityFn = Callable[[str], Entity | None]


def describe(observer: Character, entity_id: str, get_entity: GetEntityFn) -> str:
    entity = get_entity(entity_id)
    if entity is None:
        return _("someone")
    if entity.id == observer.id:
        return _("you")
    return observer.perceive(entity)
