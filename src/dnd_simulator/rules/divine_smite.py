"""Divine Smite — Paladin attack modifier (D&D 5e PHB p.85).

Pure functions: given creature and slot level, validate eligibility and build
extra damage. No state, no I/O. Slot consumption lives in CombatManager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_simulator.core.character import DamageType
from dnd_simulator.rules.combat import ExtraDamage
from dnd_simulator.rules.resources import spell_slot_pool_id

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature


def build_smite_damage(slot_level: int) -> ExtraDamage:
    """Build ExtraDamage for Divine Smite at the given spell slot level.

    D&D 5e: 2d8 radiant for a 1st-level slot, +1d8 per slot level above 1st.
    """
    dice_count = 1 + slot_level
    return ExtraDamage(dice=f"{dice_count}d8", type=DamageType.RADIANT, source="divine_smite")


def validate_smite(creature: Creature, slot_level: int) -> str | None:
    """Check if creature can Divine Smite at the given slot level.

    Returns None if valid, error string otherwise.
    """
    from dnd_simulator.core.character import Character, CharClass

    if slot_level < 1:
        return f"Invalid spell slot level: {slot_level}"

    if not isinstance(creature, Character) or creature.char_class != CharClass.PALADIN:
        return "Only a Paladin can use Divine Smite."

    pool_id = spell_slot_pool_id(slot_level)
    for pool in creature.resource_pools:
        if pool.id == pool_id:
            if pool.current_uses < 1:
                return f"No spell slot level {slot_level} remaining."
            return None

    return f"No spell slot level {slot_level} available."
