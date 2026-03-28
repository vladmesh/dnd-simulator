"""Combat resolution — resolve a single-target attack into an outcome.

Pure functions: takes numbers in, returns result out. No state mutation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from dnd_simulator.core.character import Ability, Attack, Creature, DamageType
from dnd_simulator.core.rolls import DiceResult
from dnd_simulator.rules.checks import CheckResult, attack_roll
from dnd_simulator.rules.dice import roll, roll_d20


@dataclass(frozen=True)
class ExtraDamage:
    """Additional damage source (Sneak Attack, Divine Smite, etc.)."""

    dice: str
    type: DamageType
    source: str


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


def _roll_damage(expr: str, *, critical: bool = False, rng: random.Random | None = None) -> DiceResult:
    """Roll damage dice, returning structured DiceResult. Doubles dice on crit."""
    if not critical:
        return roll(expr, rng=rng)

    # Double dice only: "2d6+3" → roll 4d6+3
    expr = expr.strip()
    parts = expr.split("d", 1)
    if len(parts) == 2 and parts[0].strip().isdigit():
        count = int(parts[0].strip())
        return roll(f"{count * 2}d{parts[1]}", rng=rng)
    # Constant (no dice) — crits don't double flat damage
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

    for comp in attack.damage:
        dr = _roll_damage(comp.dice, critical=is_crit, rng=rng)
        damage_results.append(
            DamageResult(amount=dr.total, type=comp.type, source="weapon", dice=comp.dice, dice_result=dr)
        )

    for ed in extra_damage:
        dr = _roll_damage(ed.dice, critical=is_crit, rng=rng)
        damage_results.append(
            DamageResult(amount=dr.total, type=ed.type, source=ed.source, dice=ed.dice, dice_result=dr)
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
    r = rng or random.Random()
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
