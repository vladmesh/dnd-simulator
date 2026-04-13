"""Pure functions for resource pool management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_simulator.core.character import CharClass
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


_SPELL_SLOT_TABLES: dict[CharClass, dict[int, dict[int, int]]] = {
    CharClass.PALADIN: {
        2: {1: 2},
        3: {1: 3},
        4: {1: 3},
        5: {1: 4, 2: 2},
    },
}


def build_class_resource_pools(char_class: CharClass, level: int = 1) -> list[ResourcePool]:
    """Create default resource pools for a class at a given level.

    Fighter L1: second_wind. Fighter L2+: + action_surge.
    Paladin L1: lay_on_hands only. Paladin L2+: + spell slots (half-caster table).
    """
    pools: list[ResourcePool] = []
    if char_class == CharClass.FIGHTER:
        pools.append(ResourcePool(id="second_wind", max_uses=1, current_uses=1, reset_on=RestType.SHORT_REST))
        if level >= 2:
            pools.append(ResourcePool(id="action_surge", max_uses=1, current_uses=1, reset_on=RestType.SHORT_REST))
    if char_class == CharClass.PALADIN:
        loh_max = 5 * level
        pools.append(
            ResourcePool(id="lay_on_hands", max_uses=loh_max, current_uses=loh_max, reset_on=RestType.LONG_REST)
        )
    if char_class in _SPELL_SLOT_TABLES:
        level_table = _SPELL_SLOT_TABLES[char_class]
        applicable_levels = [lv for lv in level_table if lv <= level]
        if applicable_levels:
            slot_table = level_table[max(applicable_levels)]
            pools.extend(build_spell_slot_pools(slot_table))
    return pools


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


def use_resource(creature: Creature, pool_id: str, *, amount: int = 1) -> None:
    """Consume *amount* uses of the named resource. Raises if empty, missing, or insufficient."""
    if amount < 1:
        raise ValueError(f"amount must be >= 1, got {amount}")
    for pool in creature.resource_pools:
        if pool.id == pool_id:
            if pool.current_uses < amount:
                raise ValueError(
                    f"Resource '{pool_id}' on {creature.id} has insufficient uses "
                    f"({pool.current_uses}/{pool.max_uses}, need {amount})"
                )
            pool.current_uses -= amount
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
