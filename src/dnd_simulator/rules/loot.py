"""Derived lootable state.

`is_lootable` is a pure predicate over the world's holders: a dead creature is a
lootable corpse; an open container is lootable. Centralized here so the `take`
action and awareness share one definition rather than scattering `is_alive`
checks across handlers. `loot_reach` is likewise the one combat adjacency rule,
shared by `take` validation and the combat awareness shown to the player.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from dnd_simulator.core.character import Creature, Entity
from dnd_simulator.core.container import Container
from dnd_simulator.i18n import _

if TYPE_CHECKING:
    from dnd_simulator.core.combat import BattleMap


def is_lootable(entity: Entity) -> bool:
    """Whether `entity` can currently be looted via `take`."""
    if isinstance(entity, Creature):
        return not entity.is_alive
    if isinstance(entity, Container):
        return entity.is_open
    return False


# Loot reach in combat: the holder must sit in the actor's cell or an adjacent one
# (5 ft, a single diagonal counts). Out of combat there is no grid and no reach limit.
LOOT_REACH_FT = 5


class LootBlock(StrEnum):
    """Why a lootable holder cannot be taken from in combat — also the UI reason key."""

    NOT_ON_MAP = "not_on_map"
    TOO_FAR = "too_far"


@dataclass(frozen=True)
class LootReach:
    """Loot reach of one holder in combat: distance (None off the grid) and the blocker, if any."""

    distance_ft: int | None
    block: LootBlock | None


def loot_reach(battle_map: BattleMap, actor_id: str, target_id: str) -> LootReach:
    """The single combat adjacency rule for `take`.

    The target cell is a corpse cell or a live position (`BattleMap.loot_position`);
    a holder with no cell on this fight's map (e.g. a container outside the grid) is
    not reachable in combat.
    """
    from dnd_simulator.rules.movement import grid_distance

    actor_pos = battle_map.get_position(actor_id)
    target_pos = battle_map.loot_position(target_id)
    if actor_pos is None or target_pos is None:
        return LootReach(distance_ft=None, block=LootBlock.NOT_ON_MAP)
    dist = grid_distance(actor_pos, target_pos)
    return LootReach(distance_ft=dist, block=None if dist <= LOOT_REACH_FT else LootBlock.TOO_FAR)


def loot_block_message(reach: LootReach) -> str:
    """Localised reason for a combat loot blocker."""
    if reach.block is LootBlock.TOO_FAR:
        return _("Too far to loot ({dist} ft); it must be in an adjacent cell.").format(dist=reach.distance_ft)
    return _("Out of reach in combat: it is not on the battle map.")
