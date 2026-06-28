"""Derived lootable state.

`is_lootable` is a pure predicate over the world's holders: a dead creature is a
lootable corpse; an open container is lootable. Centralized here so the `take`
action and awareness share one definition rather than scattering `is_alive`
checks across handlers.
"""

from __future__ import annotations

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.container import Container


def is_lootable(entity: Entity) -> bool:
    """Whether `entity` can currently be looted via `take`."""
    if isinstance(entity, Creature):
        return not entity.is_alive
    if isinstance(entity, Container):
        return entity.is_open
    return False
