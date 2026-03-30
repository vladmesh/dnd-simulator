"""Transport-agnostic creature action — what a brain decides to do."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ActionType(StrEnum):
    """All known action types. Values match LLM tool names."""

    IDLE = "idle"
    SAY = "say"
    ATTACK = "attack"
    DODGE = "dodge"
    FLEE = "flee"
    MOVE = "move"
    DASH = "dash"
    WAIT = "wait"
    USE_ITEM = "use_item"
    BLESS = "bless"
    EQUIP = "equip"
    UNEQUIP = "unequip"
    EQUIP_ARMOR = "equip_armor"
    UNEQUIP_ARMOR = "unequip_armor"
    EQUIP_SHIELD = "equip_shield"
    UNEQUIP_SHIELD = "unequip_shield"
    EQUIP_HEAD = "equip_head"
    UNEQUIP_HEAD = "unequip_head"
    EQUIP_FEET = "equip_feet"
    UNEQUIP_FEET = "unequip_feet"
    EQUIP_RING = "equip_ring"
    UNEQUIP_RING = "unequip_ring"
    MOVE_TO = "move_to"
    DISENGAGE = "disengage"
    SECOND_WIND = "second_wind"
    BUY = "buy"
    SELL = "sell"
    OPPORTUNITY_ATTACK = "opportunity_attack"
    END_TURN = "end_turn"
    SKIP = "skip"


@dataclass(frozen=True)
class Action:
    """A creature's chosen action for this turn.

    Params carry action-specific data (target_id, text, toward, etc.).
    """

    name: ActionType
    params: dict[str, object] = field(default_factory=dict)


# Sentinel actions — used by the multi-action turn loop.
END_TURN = Action(name=ActionType.END_TURN)
SKIP = Action(name=ActionType.SKIP)
