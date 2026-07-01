"""Sneak Attack — Rogue core mechanic (D&D 5e PHB p.96).

Pure functions: given creature/weapon data, determine eligibility and dice count.
No state, no I/O. Once-per-turn tracking lives in CombatManager.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from dnd_simulator.core.character import Attack, Character, Creature, DamageType
from dnd_simulator.core.class_features import RogueFeatures
from dnd_simulator.rules.combat import ExtraDamage

if TYPE_CHECKING:
    from dnd_simulator.core.character import Entity
    from dnd_simulator.core.combat import BattleMap


def sneak_attack_dice(creature: Creature) -> int:
    """Return the number of sneak attack d6s, or 0 if not a Rogue."""
    if not isinstance(creature, Character):
        return 0
    rogue = creature.get_feature(RogueFeatures)
    if rogue is None:
        return 0
    return rogue.sneak_attack_dice


def is_sneak_attack_weapon(attack: Attack) -> bool:
    """Check if the attack qualifies for Sneak Attack.

    D&D 5e: finesse or ranged weapon. We use reach > 10 as proxy for ranged
    (melee weapons cap at 10ft for polearms).
    """
    # Check the weapon_def for finesse flag
    # For ranged: attacks with reach > 10 are ranged
    return attack.is_finesse or attack.reach > 10


def is_sneak_attack_eligible(
    attacker: Creature,
    attack: Attack,
    *,
    has_advantage: bool,
    has_disadvantage: bool,
    ally_adjacent_to_target: bool,
) -> bool:
    """Determine if Sneak Attack can trigger on this attack.

    Conditions (PHB p.96):
    1. Attacker is a Rogue with sneak_attack_dice > 0
    2. Weapon is finesse or ranged
    3. Has advantage on the attack roll (and no disadvantage cancelling it)
       OR an enemy of the target (ally of attacker) is within 5ft of target
    4. Does NOT have disadvantage (if relying on advantage, advantage must be net)

    Once-per-turn check is NOT done here — that's state, handled by CombatManager.
    """
    if sneak_attack_dice(attacker) == 0:
        return False

    if not is_sneak_attack_weapon(attack):
        return False

    # D&D 5e: if you have advantage (and it wasn't cancelled by disadvantage), SA triggers.
    # If you DON'T have advantage, you can still SA if an ally is adjacent — but NOT if
    # you have disadvantage.
    if has_advantage and not has_disadvantage:
        return True

    return ally_adjacent_to_target and not has_disadvantage


def find_adjacent_ally(
    attacker_id: str,
    target_id: str,
    battle_map: BattleMap,
    entities: Mapping[str, Entity],
    is_ally: Callable[[str], bool],
) -> bool:
    """Check if any alive ally of the attacker is within 5ft of the target.

    Pure function — takes battle map positions and an ally predicate.
    """
    from dnd_simulator.rules.movement import grid_distance

    target_pos = battle_map.get_position(target_id)
    if target_pos is None:
        return False

    for eid, pos in battle_map.positions.items():
        if eid in (attacker_id, target_id):
            continue
        e = entities.get(eid)
        if not isinstance(e, Creature) or not e.is_alive:
            continue
        if grid_distance(target_pos, pos) > 5:
            continue
        if is_ally(eid):
            return True
    return False


def check_sneak_attack(
    attacker: Creature,
    attack: Attack,
    *,
    advantage: bool,
    disadvantage: bool,
    already_used: bool,
    ally_adjacent: bool,
) -> tuple[ExtraDamage, ...]:
    """Full sneak attack check: eligibility + ExtraDamage construction.

    Combines dice count, weapon check, eligibility, and builds the ExtraDamage
    tuple. Once-per-turn tracking (already_used) is passed in from the caller.
    """
    sa_dice = sneak_attack_dice(attacker)
    if sa_dice == 0 or already_used:
        return ()

    if not is_sneak_attack_eligible(
        attacker,
        attack,
        has_advantage=advantage,
        has_disadvantage=disadvantage,
        ally_adjacent_to_target=ally_adjacent,
    ):
        return ()

    sa_expr = f"{sa_dice}d6"
    reason = "advantage" if advantage else "ally_adjacent"
    return (ExtraDamage(dice=sa_expr, type=DamageType.PIERCING, source="sneak_attack", reason=reason),)
