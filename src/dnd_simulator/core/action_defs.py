"""Centralized action definitions — single source of truth for action metadata.

Each ActionType gets an ActionDef with description, cost, params, combat mode,
and flags. Consumers (LLM tools, frontend, validation, cost calculation) read
from this registry instead of maintaining their own scattered constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dnd_simulator.core.action import ActionType
from dnd_simulator.i18n import N_


class CostType(StrEnum):
    FREE = "free"
    ACTION = "action"
    BONUS_ACTION = "bonus_action"
    MOVEMENT = "movement"
    REACTION = "reaction"


class CombatMode(StrEnum):
    ANY = "any"
    COMBAT_ONLY = "combat_only"
    PEACEFUL_ONLY = "peaceful_only"


class TargetMode(StrEnum):
    NONE = "none"  # no creature target (equip, say, wait, etc.)
    SELF = "self"  # target = caster, implicit (dodge, dash, second_wind)
    SINGLE = "single"  # pick 1 creature (attack, lay_on_hands)


class TargetScope(StrEnum):
    HOSTILE = "hostile"  # enemies only
    ALLY = "ally"  # allies + self
    ANY = "any"  # everyone + self


@dataclass(frozen=True)
class ParamDef:
    """Definition of a single action parameter."""

    name: str
    param_type: str  # JSON Schema type: "string", "integer"
    description: str
    required: bool = False


@dataclass(frozen=True)
class CostOverride:
    """An alternative cost a class feature grants for an action.

    E.g. Rogue Cunning Action: DASH/DISENGAGE as bonus_action.
    The brain/player chooses which cost to use via ``cost_mode`` param.
    """

    action_type: ActionType
    cost_type: CostType
    source: str  # "cunning_action", "quickened_spell", etc.


@dataclass(frozen=True)
class ActionDef:
    """Metadata for a single ActionType — the single source of truth."""

    action_type: ActionType
    description: str  # English base; mark with N_() for .po extraction
    cost_type: CostType
    combat_mode: CombatMode = CombatMode.ANY
    params: tuple[ParamDef, ...] = ()
    llm_hint: str = ""  # overrides description for LLM tool schema
    target_mode: TargetMode = TargetMode.NONE
    target_scope: TargetScope = TargetScope.HOSTILE
    ends_peaceful_turn: bool = False
    internal: bool = False  # END_TURN, SKIP — excluded from LLM/frontend
    provider_managed: bool = False  # excluded from BaseActionProvider probing

    @property
    def targeted(self) -> bool:
        """Backwards-compatible: True when action requires a creature target."""
        return self.target_mode == TargetMode.SINGLE


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ACTION_DEFS: dict[ActionType, ActionDef] = {}


def _reg(d: ActionDef) -> None:
    ACTION_DEFS[d.action_type] = d


def get_action_def(action_type: ActionType) -> ActionDef:
    """Look up ActionDef. Crashes if missing — every ActionType must be registered."""
    return ACTION_DEFS[action_type]


# ---------------------------------------------------------------------------
# Registrations — one per ActionType
# ---------------------------------------------------------------------------

_reg(
    ActionDef(
        action_type=ActionType.IDLE,
        description=N_("Do nothing this turn."),
        cost_type=CostType.FREE,
        combat_mode=CombatMode.PEACEFUL_ONLY,
        ends_peaceful_turn=True,
        params=(ParamDef("description", "string", N_("Flavor text")),),
        llm_hint="Do nothing this turn. Use when there is nothing meaningful to do.",
    )
)

_reg(
    ActionDef(
        action_type=ActionType.SAY,
        description=N_("Say something out loud."),
        cost_type=CostType.FREE,
        combat_mode=CombatMode.PEACEFUL_ONLY,
        ends_peaceful_turn=True,
        params=(ParamDef("text", "string", N_("What to say (in character)"), required=True),),
        llm_hint="Say something out loud. Use for dialog, greetings, threats, etc.",
    )
)

_reg(
    ActionDef(
        action_type=ActionType.ATTACK,
        description=N_("Attack a target with your equipped weapon or fists."),
        cost_type=CostType.ACTION,
        target_mode=TargetMode.SINGLE,
        target_scope=TargetScope.HOSTILE,
        ends_peaceful_turn=True,
        params=(
            ParamDef("target_id", "string", N_("ID of the target entity"), required=True),
            ParamDef("description", "string", N_("Flavor text for the attack")),
            ParamDef(
                "smite_slot_level",
                "integer",
                N_("Spell slot level to spend on Divine Smite (Paladin only, adds radiant damage on hit)"),
            ),
        ),
        llm_hint=(
            "Attack a target with your equipped weapon (or fists if unarmed). Target must be within weapon reach. "
            "Paladins can add smite_slot_level (integer) to spend a spell slot on Divine Smite — "
            "adds 2d8 radiant damage on hit (slot spent only if you hit)."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.DODGE,
        description=N_("Take a defensive stance. Attacks against you have disadvantage until your next turn."),
        cost_type=CostType.ACTION,
        combat_mode=CombatMode.COMBAT_ONLY,
        target_mode=TargetMode.SELF,
        ends_peaceful_turn=True,
        params=(ParamDef("description", "string", N_("Flavor text")),),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.FLEE,
        description=N_("Try to escape from combat."),
        cost_type=CostType.ACTION,
        combat_mode=CombatMode.COMBAT_ONLY,
        target_mode=TargetMode.SELF,
        ends_peaceful_turn=True,
        params=(ParamDef("description", "string", N_("Flavor text")),),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.MOVE,
        description=N_("Move up to your speed."),
        cost_type=CostType.MOVEMENT,
        combat_mode=CombatMode.COMBAT_ONLY,
        ends_peaceful_turn=True,
        params=(
            ParamDef("toward", "string", N_("ID of entity to move toward")),
            ParamDef("away_from", "string", N_("ID of entity to move away from")),
            ParamDef("direction", "string", N_("Compass direction: north, south, east, west, etc.")),
            ParamDef("description", "string", N_("Flavor text")),
        ),
        llm_hint=(
            "Move up to your speed (in feet). Use toward/away_from with a target ID, "
            "or direction (north/south/east/west/northeast/northwest/southeast/southwest)."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.MOVE_TO,
        description=N_("Move to a specific position on the battle map."),
        cost_type=CostType.FREE,  # handler manages movement budget directly (like dash)
        combat_mode=CombatMode.COMBAT_ONLY,
        params=(
            ParamDef("x", "integer", N_("Target X coordinate in feet"), required=True),
            ParamDef("y", "integer", N_("Target Y coordinate in feet"), required=True),
        ),
        llm_hint=(
            "Move to exact grid coordinates (x, y) in feet. Use when you know the exact position. "
            "Pathfinding is automatic — finds the shortest path around walls and occupied cells."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.DASH,
        description=N_("Sprint: move up to double your speed. Costs 1 action."),
        cost_type=CostType.ACTION,
        combat_mode=CombatMode.COMBAT_ONLY,
        target_mode=TargetMode.SELF,
        ends_peaceful_turn=True,
        params=(
            ParamDef("toward", "string", N_("ID of entity to dash toward")),
            ParamDef("away_from", "string", N_("ID of entity to dash away from")),
            ParamDef("direction", "string", N_("Compass direction: north, south, east, west, etc.")),
            ParamDef("description", "string", N_("Flavor text")),
            ParamDef("cost_mode", "string", N_("Cost variant: action or bonus_action")),
        ),
        llm_hint=(
            "Sprint: move up to DOUBLE your speed. Uses your action — you cannot attack this turn. "
            "Same parameters as move. Rogues can pass cost_mode=bonus_action via Cunning Action."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.DISENGAGE,
        description=N_("Your movement doesn't provoke opportunity attacks this turn."),
        cost_type=CostType.ACTION,
        combat_mode=CombatMode.COMBAT_ONLY,
        target_mode=TargetMode.SELF,
        ends_peaceful_turn=True,
        params=(ParamDef("cost_mode", "string", N_("Cost variant: action or bonus_action")),),
        llm_hint=(
            "Disengage: your movement doesn't provoke opportunity attacks this turn. "
            "Costs 1 action. Rogues can pass cost_mode=bonus_action via Cunning Action."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.WAIT,
        description=N_("Wait for a period of time."),
        cost_type=CostType.FREE,
        combat_mode=CombatMode.PEACEFUL_ONLY,
        ends_peaceful_turn=True,
        params=(
            ParamDef("hours", "integer", N_("How many hours to wait (default: 1)")),
            ParamDef("travel_to", "string", N_("Location ID to travel to instead of waiting in place")),
        ),
        llm_hint="Wait and do nothing for a period of time. Useful when nothing is happening.",
    )
)

_reg(
    ActionDef(
        action_type=ActionType.USE_ITEM,
        description=N_("Use a consumable item from your inventory."),
        cost_type=CostType.ACTION,
        ends_peaceful_turn=True,
        provider_managed=True,
        params=(ParamDef("item_id", "string", N_("ID of the item to use"), required=True),),
        llm_hint=(
            "Use a consumable item from your inventory (potion, scroll, etc.). Costs 1 action. Item is consumed."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.BLESS,
        description=N_("Invoke a blessing. Grants +d4 to attack rolls for several rounds."),
        cost_type=CostType.BONUS_ACTION,
        target_mode=TargetMode.SELF,
        provider_managed=True,
        llm_hint=(
            "Invoke a blessing from your weapon. Costs a bonus action. "
            "Grants +d4 to all your attack rolls for several rounds."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.EQUIP,
        description=N_("Equip a weapon from your inventory."),
        cost_type=CostType.FREE,
        ends_peaceful_turn=True,
        provider_managed=True,
        params=(ParamDef("weapon_id", "string", N_("ID of the weapon to equip"), required=True),),
        llm_hint=(
            "Equip a weapon from your inventory. Free action. "
            "Attacking with a weapon deals more damage than fists. "
            "Your current weapon (if any) goes back to inventory."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.UNEQUIP,
        description=N_("Put away your equipped weapon. You will fight with fists."),
        cost_type=CostType.FREE,
        ends_peaceful_turn=True,
        provider_managed=True,
    )
)

_reg(
    ActionDef(
        action_type=ActionType.EQUIP_ARMOR,
        description=N_("Equip armor from your inventory."),
        cost_type=CostType.FREE,
        provider_managed=True,
        params=(ParamDef("armor_id", "string", N_("ID of the armor to equip"), required=True),),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.UNEQUIP_ARMOR,
        description=N_("Remove your equipped armor."),
        cost_type=CostType.FREE,
        provider_managed=True,
    )
)

_reg(
    ActionDef(
        action_type=ActionType.EQUIP_SHIELD,
        description=N_("Equip a shield from your inventory. +2 AC."),
        cost_type=CostType.FREE,
        provider_managed=True,
        params=(ParamDef("shield_id", "string", N_("ID of the shield to equip"), required=True),),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.UNEQUIP_SHIELD,
        description=N_("Remove your equipped shield."),
        cost_type=CostType.FREE,
        provider_managed=True,
    )
)

_reg(
    ActionDef(
        action_type=ActionType.EQUIP_HEAD,
        description=N_("Equip headgear from your inventory."),
        cost_type=CostType.FREE,
        provider_managed=True,
        params=(ParamDef("head_id", "string", N_("ID of the headgear to equip"), required=True),),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.UNEQUIP_HEAD,
        description=N_("Remove your equipped headgear."),
        cost_type=CostType.FREE,
        provider_managed=True,
    )
)

_reg(
    ActionDef(
        action_type=ActionType.EQUIP_FEET,
        description=N_("Equip footwear from your inventory."),
        cost_type=CostType.FREE,
        provider_managed=True,
        params=(ParamDef("feet_id", "string", N_("ID of the footwear to equip"), required=True),),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.UNEQUIP_FEET,
        description=N_("Remove your equipped footwear."),
        cost_type=CostType.FREE,
        provider_managed=True,
    )
)

_reg(
    ActionDef(
        action_type=ActionType.EQUIP_RING,
        description=N_("Equip a ring from your inventory."),
        cost_type=CostType.FREE,
        provider_managed=True,
        params=(ParamDef("ring_id", "string", N_("ID of the ring to equip"), required=True),),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.UNEQUIP_RING,
        description=N_("Remove your equipped ring."),
        cost_type=CostType.FREE,
        provider_managed=True,
    )
)

_reg(
    ActionDef(
        action_type=ActionType.SECOND_WIND,
        description=N_("Heal yourself for 1d10 + fighter level HP. Once per short rest."),
        cost_type=CostType.BONUS_ACTION,
        target_mode=TargetMode.SELF,
        provider_managed=True,
        llm_hint=(
            "Second Wind: heal yourself for 1d10 + your fighter level HP. Costs a bonus action. Once per short rest."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.ACTION_SURGE,
        description=N_("Gain one additional Action this turn. Once per short rest."),
        cost_type=CostType.BONUS_ACTION,
        combat_mode=CombatMode.COMBAT_ONLY,
        target_mode=TargetMode.SELF,
        provider_managed=True,
        llm_hint=("Action Surge: spend a bonus action to gain one additional Action this turn. Once per short rest."),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.BUY,
        description=N_("Buy an item from a merchant."),
        cost_type=CostType.FREE,
        combat_mode=CombatMode.PEACEFUL_ONLY,
        provider_managed=True,
        params=(
            ParamDef("merchant_id", "string", N_("ID of the merchant NPC"), required=True),
            ParamDef("item_id", "string", N_("ID of the item to buy"), required=True),
        ),
        llm_hint="Buy an item from a merchant's inventory. You must be at the same location and have enough gold.",
    )
)

_reg(
    ActionDef(
        action_type=ActionType.SELL,
        description=N_("Sell an item to a merchant."),
        cost_type=CostType.FREE,
        combat_mode=CombatMode.PEACEFUL_ONLY,
        provider_managed=True,
        params=(
            ParamDef("merchant_id", "string", N_("ID of the merchant NPC"), required=True),
            ParamDef("item_id", "string", N_("ID of the item to sell"), required=True),
        ),
        llm_hint="Sell an item from your inventory to a merchant. You must be at the same location.",
    )
)

_reg(
    ActionDef(
        action_type=ActionType.LAY_ON_HANDS,
        description=N_("Lay on Hands: spend HP from your healing pool to heal a creature."),
        cost_type=CostType.ACTION,
        target_mode=TargetMode.SINGLE,
        target_scope=TargetScope.ALLY,
        provider_managed=True,
        params=(
            ParamDef("target_id", "string", N_("ID of creature to heal (omit for self)")),
            ParamDef("amount", "integer", N_("HP to spend from pool"), required=True),
        ),
        llm_hint=(
            "Lay on Hands: spend points from your divine healing pool to restore HP. "
            "Touch range — self or adjacent creature. Choose how many points to spend (1 to pool remaining)."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.LONG_REST,
        description=N_("Take a long rest: heal to full, restore all resources. Takes 8 hours."),
        cost_type=CostType.FREE,
        combat_mode=CombatMode.PEACEFUL_ONLY,
        target_mode=TargetMode.SELF,
        ends_peaceful_turn=True,
        llm_hint=(
            "Long rest: heal to full HP, restore all resource pools (spell slots, Second Wind, etc.). "
            "Takes 8 hours. Only available outside combat."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.SHORT_REST,
        description=N_("Take a short rest: restore short-rest resources. Takes 1 hour."),
        cost_type=CostType.FREE,
        combat_mode=CombatMode.PEACEFUL_ONLY,
        target_mode=TargetMode.SELF,
        ends_peaceful_turn=True,
        llm_hint=(
            "Short rest: restore short-rest resources (e.g. Second Wind). "
            "Does NOT heal HP or restore spell slots. Takes 1 hour. Only available outside combat."
        ),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.OPPORTUNITY_ATTACK,
        description=N_("Make a melee attack as a reaction when a creature leaves your reach."),
        cost_type=CostType.REACTION,
        combat_mode=CombatMode.COMBAT_ONLY,
        target_mode=TargetMode.SINGLE,
        target_scope=TargetScope.HOSTILE,
        internal=True,  # not offered by providers — triggered by movement only
        params=(ParamDef("target_id", "string", N_("Target creature ID"), required=True),),
    )
)

_reg(
    ActionDef(
        action_type=ActionType.END_TURN,
        description=N_("End your turn."),
        cost_type=CostType.FREE,
        internal=True,
    )
)

_reg(
    ActionDef(
        action_type=ActionType.SKIP,
        description=N_("Skip (system use)."),
        cost_type=CostType.FREE,
        internal=True,
    )
)
