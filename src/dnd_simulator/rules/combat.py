"""Combat resolution — resolve a single-target attack into an outcome.

Pure functions: takes numbers in, returns result out. No state mutation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from dnd_simulator.core.character import Ability, Attack, Creature, DamageType
from dnd_simulator.core.rolls import DiceResult
from dnd_simulator.rules.checks import CheckResult, attack_roll
from dnd_simulator.rules.dice import get_global_rng, roll, roll_d20


@dataclass(frozen=True)
class ExtraDamage:
    """Additional damage source (Sneak Attack, Divine Smite, etc.)."""

    dice: str
    type: DamageType
    source: str
    reason: str | None = None


@dataclass(frozen=True)
class DamageResult:
    """Damage dealt by a single component."""

    amount: int
    type: DamageType
    source: str = ""
    dice: str = ""
    dice_result: DiceResult | None = None  # individual die faces for UI breakdown


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


def _roll_damage(expr: str, *, reroll_below: int = 0, rng: random.Random | None = None) -> DiceResult:
    """Roll damage dice, returning structured DiceResult."""
    return roll(expr, reroll_below=reroll_below, rng=rng)


def _roll_crit_damage(expr: str, *, rng: random.Random | None = None) -> DiceResult | None:
    """Roll extra crit dice (same expression, no GWF reroll)."""
    return roll(expr, rng=rng)


def resolve_attack(
    modifier: int,
    ac: int,
    attack: Attack,
    *,
    damage_bonus: int = 0,
    extra_damage: tuple[ExtraDamage, ...] = (),
    advantage: bool = False,
    disadvantage: bool = False,
    force_crit: bool = False,
    gwf_reroll: bool = False,
    rng: random.Random | None = None,
) -> AttackResult:
    """Resolve a single-target attack.

    Args:
        modifier: attacker's ability modifier for this attack
        ac: target's armor class
        attack: the Attack being used (contains damage components and resolve type)
        extra_damage: additional labeled damage sources (Sneak Attack, Smite, etc.)
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
    is_crit = (check.critical and check.success) or (check.success and force_crit)
    damage_results: list[DamageResult] = []

    reroll_below = 2 if gwf_reroll else 0
    for comp in attack.damage:
        # Base damage (with GWF reroll)
        dr = _roll_damage(comp.dice, reroll_below=reroll_below, rng=rng)
        damage_results.append(
            DamageResult(amount=dr.total, type=comp.type, source="weapon", dice=comp.dice, dice_result=dr)
        )
        # Crit dice — same dice expression, NO GWF reroll
        if is_crit:
            crit_dr = _roll_crit_damage(comp.dice, rng=rng)
            if crit_dr is not None:
                damage_results.append(
                    DamageResult(
                        amount=crit_dr.total, type=comp.type, source="weapon_crit", dice=comp.dice, dice_result=crit_dr
                    )
                )

    for ed in extra_damage:
        # Base extra damage (no GWF on extra damage)
        dr = _roll_damage(ed.dice, rng=rng)
        damage_results.append(
            DamageResult(amount=dr.total, type=ed.type, source=ed.source, dice=ed.dice, dice_result=dr)
        )
        # Crit dice for extra damage
        if is_crit:
            crit_dr = _roll_crit_damage(ed.dice, rng=rng)
            if crit_dr is not None:
                damage_results.append(
                    DamageResult(
                        amount=crit_dr.total,
                        type=ed.type,
                        source=f"{ed.source}_crit",
                        dice=ed.dice,
                        dice_result=crit_dr,
                    )
                )

    # Flat damage bonus (e.g. Dueling +2) — not doubled on crit
    total = sum(d.amount for d in damage_results) + damage_bonus

    return AttackResult(
        hit=True,
        critical=is_crit,
        attack_check=check,
        damage=tuple(damage_results),
        total_damage=total,
    )


def roll_initiative(
    creatures: list[Creature],
    *,
    rng: random.Random | None = None,
) -> list[Creature]:
    """Roll initiative for each creature: d20 + DEX modifier.

    Ties broken by higher DEX score, then random tiebreaker.
    Returns creatures sorted from highest to lowest initiative.
    """
    r = rng if rng is not None else get_global_rng()
    rolls: list[tuple[Creature, int, int, int]] = []
    for c in creatures:
        d20_result = roll_d20(rng=r)
        modifier = c.ability_scores.modifier(Ability.DEX)
        total = d20_result.natural + modifier
        dex_score = c.ability_scores[Ability.DEX]
        tiebreaker = r.randint(0, 1_000_000)
        rolls.append((c, total, dex_score, tiebreaker))

    rolls.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
    return [c for c, _, _, _ in rolls]
