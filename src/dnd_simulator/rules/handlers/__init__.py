"""Action handlers package — re-exports all public handlers."""

from dnd_simulator.rules.handlers.action_surge import handle_action_surge
from dnd_simulator.rules.handlers.combat import handle_attack, handle_dodge, handle_flee
from dnd_simulator.rules.handlers.equipment import (
    EQUIPMENT_HANDLERS,
    SLOT_CONFIGS,
    SlotConfig,
    handle_equip,
    handle_unequip,
)
from dnd_simulator.rules.handlers.items import (
    handle_bless,
    handle_idle,
    handle_lay_on_hands,
    handle_say,
    handle_second_wind,
    handle_use_item,
)
from dnd_simulator.rules.handlers.loot import handle_take
from dnd_simulator.rules.handlers.movement import (
    handle_dash,
    handle_disengage,
    handle_move,
    handle_move_to,
    handle_wait,
)
from dnd_simulator.rules.handlers.reactions import handle_opportunity_attack
from dnd_simulator.rules.handlers.rest import handle_long_rest, handle_short_rest
from dnd_simulator.rules.handlers.trade import handle_buy, handle_sell

__all__ = [
    "EQUIPMENT_HANDLERS",
    "SLOT_CONFIGS",
    "SlotConfig",
    "handle_action_surge",
    "handle_attack",
    "handle_bless",
    "handle_buy",
    "handle_dash",
    "handle_disengage",
    "handle_dodge",
    "handle_equip",
    "handle_flee",
    "handle_idle",
    "handle_lay_on_hands",
    "handle_long_rest",
    "handle_move",
    "handle_move_to",
    "handle_opportunity_attack",
    "handle_say",
    "handle_second_wind",
    "handle_sell",
    "handle_short_rest",
    "handle_take",
    "handle_unequip",
    "handle_use_item",
    "handle_wait",
]
