"""Pure functions for resource pool management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_simulator.core.resource import ResourcePool, RestType

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature

_SPELL_SLOT_PREFIX = "spell_slot_"


def spell_slot_pool_id(level: int) -> str:
    """Return the canonical pool id for a spell slot level."""
    return f"{_SPELL_SLOT_PREFIX}{level}"


def build_spell_slot_pools(slot_table: dict[int, int]) -> list[ResourcePool]:
    """Build ResourcePools from a spell slot table {level: count}.

    All spell slots reset on long rest per D&D 5e rules.
    """
    return [
        ResourcePool(
            id=spell_slot_pool_id(level),
            max_uses=count,
            current_uses=count,
            reset_on=RestType.LONG_REST,
        )
        for level, count in sorted(slot_table.items())
    ]


def get_available_spell_slots(creature: Creature) -> dict[int, int]:
    """Return {level: remaining_uses} for all non-exhausted spell slot pools."""
    result: dict[int, int] = {}
    for pool in creature.resource_pools:
        if pool.id.startswith(_SPELL_SLOT_PREFIX) and pool.current_uses > 0:
            level = int(pool.id[len(_SPELL_SLOT_PREFIX) :])
            result[level] = pool.current_uses
    return result


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
