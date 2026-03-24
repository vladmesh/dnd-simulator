"""Pure functions for resource pool management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_simulator.core.resource import RestType

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature


def has_resource(creature: Creature, pool_id: str) -> bool:
    """Check if creature has at least 1 use of the named resource."""
    for pool in creature.resource_pools:
        if pool.id == pool_id:
            return pool.current_uses > 0
    raise KeyError(f"No resource pool '{pool_id}' on {creature.id}")


def use_resource(creature: Creature, pool_id: str) -> None:
    """Consume 1 use of the named resource. Raises if empty or missing."""
    for pool in creature.resource_pools:
        if pool.id == pool_id:
            if pool.current_uses <= 0:
                raise ValueError(f"Resource '{pool_id}' on {creature.id} is exhausted (0/{pool.max_uses})")
            pool.current_uses -= 1
            return
    raise KeyError(f"No resource pool '{pool_id}' on {creature.id}")


def reset_resources(creature: Creature, rest_type: RestType) -> list[str]:
    """Reset all resource pools that match the rest type. Returns list of reset pool ids.

    D&D 5e: long rest resets everything that short rest does, plus long-rest-only pools.
    """
    reset_ids: list[str] = []
    for pool in creature.resource_pools:
        should_reset = pool.reset_on == rest_type or (
            rest_type == RestType.LONG_REST and pool.reset_on == RestType.SHORT_REST
        )
        if should_reset and pool.current_uses < pool.max_uses:
            pool.current_uses = pool.max_uses
            reset_ids.append(pool.id)
    return reset_ids
