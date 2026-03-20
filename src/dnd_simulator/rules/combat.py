"""Combat resolution — resolve a single-target attack into an outcome.

Pure function: takes numbers in, returns result out. No state mutation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from dnd_simulator.core.character import Attack, DamageType
from dnd_simulator.rules.checks import CheckResult, attack_roll, damage_roll


@dataclass(frozen=True)
class DamageResult:
    """Damage dealt by a single component."""

    amount: int
    type: DamageType


@dataclass(frozen=True)
class AttackResult:
    """Full outcome of a resolved attack."""

    hit: bool
    critical: bool
    attack_check: CheckResult
    damage: tuple[DamageResult, ...]  # empty if miss
    total_damage: int  # sum of all components

    @property
    def miss(self) -> bool:
        return not self.hit


def resolve_attack(
    modifier: int,
    ac: int,
    attack: Attack,
    *,
    extra_damage: tuple[tuple[str, DamageType], ...] = (),
    advantage: bool = False,
    disadvantage: bool = False,
    rng: random.Random | None = None,
) -> AttackResult:
    """Resolve a single-target attack.

    Args:
        modifier: attacker's ability modifier for this attack
        ac: target's armor class
        attack: the Attack being used (contains damage components and resolve type)
        extra_damage: additional damage components (e.g. smite) as (dice_expr, type) tuples
        advantage: roll with advantage
        disadvantage: roll with disadvantage
        rng: random source for reproducible tests
    """
    from dnd_simulator.core.character import ResolveType

    # Auto-hit attacks (e.g. Magic Missile) skip the attack roll
    if attack.resolve == ResolveType.AUTO_HIT:
        check = CheckResult(success=True, roll=0, total=0, dc=ac, critical=False)
    else:
        check = attack_roll(modifier, ac, advantage=advantage, disadvantage=disadvantage, rng=rng)

    if not check.success:
        return AttackResult(
            hit=False,
            critical=False,
            attack_check=check,
            damage=(),
            total_damage=0,
        )

    # Roll damage for each component
    is_crit = check.critical and check.success
    damage_results: list[DamageResult] = []

    for comp in attack.damage:
        amount = damage_roll(comp.dice, critical=is_crit, rng=rng)
        damage_results.append(DamageResult(amount=amount, type=comp.type))

    for dice_expr, dmg_type in extra_damage:
        amount = damage_roll(dice_expr, critical=is_crit, rng=rng)
        damage_results.append(DamageResult(amount=amount, type=dmg_type))

    total = sum(d.amount for d in damage_results)

    return AttackResult(
        hit=True,
        critical=is_crit,
        attack_check=check,
        damage=tuple(damage_results),
        total_damage=total,
    )
