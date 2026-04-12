"""Modifier pipeline — centralized derived stat computation.

Collects modifiers from conditions, equipment, and (future) spells/class features.
Computes effective stats (AC, speed, attack roll) via pure functions.

Replaces ad-hoc stat computation scattered across combat_manager, conditions.py, etc.
"""

from __future__ import annotations

from dnd_simulator.core.character import Ability, Character, Creature
from dnd_simulator.core.conditions import Condition, ConditionsMap
from dnd_simulator.core.modifiers import AttackModifiers, Modifier, ModifierOp, RollComponent, StatType
from dnd_simulator.rules.proficiency import (
    is_proficient_with_armor,
    is_proficient_with_shield,
    is_proficient_with_weapon,
    proficiency_bonus,
)
from dnd_simulator.rules.weapons import get_weapon_attack, get_weapon_modifier

# ---------------------------------------------------------------------------
# Condition → Modifier mapping (declarative)
# ---------------------------------------------------------------------------
# "self" modifiers affect the creature's own stats.
# "defense" modifiers affect attacks/checks AGAINST the creature.

_CONDITION_SELF_MODIFIERS: dict[Condition, tuple[Modifier, ...]] = {
    Condition.BLINDED: (Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="blinded"),),
    Condition.FRIGHTENED: (Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="frightened"),),
    Condition.GRAPPLED: (Modifier(StatType.SPEED, ModifierOp.OVERRIDE, value=0, source="grappled"),),
    Condition.INVISIBLE: (Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="invisible"),),
    Condition.PARALYZED: (Modifier(StatType.SPEED, ModifierOp.OVERRIDE, value=0, source="paralyzed"),),
    Condition.PETRIFIED: (Modifier(StatType.SPEED, ModifierOp.OVERRIDE, value=0, source="petrified"),),
    Condition.POISONED: (Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="poisoned"),),
    Condition.PRONE: (Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="prone"),),
    Condition.RESTRAINED: (
        Modifier(StatType.SPEED, ModifierOp.OVERRIDE, value=0, source="restrained"),
        Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="restrained"),
    ),
    Condition.STUNNED: (Modifier(StatType.SPEED, ModifierOp.OVERRIDE, value=0, source="stunned"),),
    Condition.UNCONSCIOUS: (Modifier(StatType.SPEED, ModifierOp.OVERRIDE, value=0, source="unconscious"),),
    Condition.BLESSED: (Modifier(StatType.ATTACK_ROLL, ModifierOp.ADD, dice="1d4", source="blessed"),),
}

_CONDITION_DEFENSE_MODIFIERS: dict[Condition, tuple[Modifier, ...]] = {
    Condition.BLINDED: (Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="target_blinded"),),
    Condition.INVISIBLE: (Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="target_invisible"),),
    Condition.PARALYZED: (Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="target_paralyzed"),),
    Condition.PETRIFIED: (Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="target_petrified"),),
    Condition.PRONE: (
        Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="target_prone", melee_only=True),
        Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="target_prone", ranged_only=True),
    ),
    Condition.RESTRAINED: (Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="target_restrained"),),
    Condition.STUNNED: (Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="target_stunned"),),
    Condition.UNCONSCIOUS: (Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="target_unconscious"),),
    Condition.DODGING: (Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="target_dodging"),),
}

# Melee hits against these conditions are auto-crits (not a stat modifier).
_AUTO_CRIT_MELEE: frozenset[Condition] = frozenset({Condition.PARALYZED, Condition.UNCONSCIOUS})


# ---------------------------------------------------------------------------
# Modifier collection
# ---------------------------------------------------------------------------


def collect_self_modifiers(creature: Creature) -> list[Modifier]:
    """Gather modifiers that affect the creature's own stats.

    Sources: conditions, equipment, armor proficiency.
    """
    mods: list[Modifier] = []
    for condition in creature.conditions:
        mods.extend(_CONDITION_SELF_MODIFIERS.get(condition, ()))

    # Weapon magic bonus
    weapon_mod = get_weapon_modifier(creature)
    if weapon_mod:
        mods.append(Modifier(StatType.ATTACK_ROLL, ModifierOp.ADD, value=weapon_mod, source="weapon_magic"))

    # Non-proficient armor/shield → disadvantage on attack rolls (D&D 5e PHB p.144)
    if isinstance(creature, Character):
        if (
            creature.equipped_armor
            and creature.equipped_armor.armor_def
            and not is_proficient_with_armor(creature.char_class, creature.equipped_armor.armor_def)
        ):
            mods.append(Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="non_proficient_armor"))
        if (
            creature.equipped_shield
            and creature.equipped_shield.shield_def
            and not is_proficient_with_shield(creature.char_class)
        ):
            mods.append(Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="non_proficient_shield"))

        # Class-feature-driven modifiers (fighting styles, etc.)
        for feature in creature.class_features:
            mods.extend(feature.collect_self_modifiers(creature))

    # Accessory modifiers (head, feet, ring)
    for slot_field in ("equipped_head", "equipped_feet", "equipped_ring"):
        item = getattr(creature, slot_field, None)
        if item is not None and item.accessory_def is not None:
            mods.extend(item.accessory_def.grant_modifiers)

    return mods


def collect_defense_modifiers(creature: Creature) -> list[Modifier]:
    """Gather modifiers that affect attacks/checks AGAINST the creature.

    Sources: conditions, equipment. Future: spells, class features.
    """
    mods: list[Modifier] = []
    for condition in creature.conditions:
        mods.extend(_CONDITION_DEFENSE_MODIFIERS.get(condition, ()))
    return mods


# ---------------------------------------------------------------------------
# Pipeline functions
# ---------------------------------------------------------------------------


def compute_stat(base: int, modifiers: list[Modifier], stat: StatType) -> int:
    """Compute a derived stat value from base + modifiers.

    Pipeline order:
    1. OVERRIDE → most restrictive wins (min value)
    2. ADD → group by source (same source doesn't stack, take highest), sum
    """
    relevant = [m for m in modifiers if m.stat == stat]

    # OVERRIDE wins — force final value, take most restrictive
    overrides = [m for m in relevant if m.op == ModifierOp.OVERRIDE]
    if overrides:
        return min(m.value for m in overrides)

    # ADD — same source doesn't stack (take highest per source)
    by_source: dict[str | int, int] = {}
    for m in relevant:
        if m.op != ModifierOp.ADD:
            continue
        key: str | int = m.source if m.source else id(m)  # sourceless always stack
        if key in by_source:
            by_source[key] = max(by_source[key], m.value)
        else:
            by_source[key] = m.value

    return base + sum(by_source.values())


def collect_dice_bonuses(modifiers: list[Modifier], stat: StatType) -> tuple[str, ...]:
    """Collect dice expressions from ADD modifiers (e.g. "1d4" from Bless)."""
    return tuple(m.dice for m in modifiers if m.stat == stat and m.op == ModifierOp.ADD and m.dice)


def resolve_advantage(
    modifiers: list[Modifier],
    stat: StatType,
    *,
    melee: bool = True,
) -> tuple[bool, bool]:
    """Resolve advantage/disadvantage from modifiers.

    D&D 5e: any advantage + any disadvantage = flat roll (both cancel).
    Returns (has_advantage, has_disadvantage).
    """
    has_adv = False
    has_dis = False
    for m in modifiers:
        if m.stat != stat:
            continue
        if m.melee_only and not melee:
            continue
        if m.ranged_only and melee:
            continue
        if m.op == ModifierOp.ADVANTAGE:
            has_adv = True
        elif m.op == ModifierOp.DISADVANTAGE:
            has_dis = True

    # D&D 5e cancellation: any amount of each = flat roll
    if has_adv and has_dis:
        return (False, False)
    return (has_adv, has_dis)


def is_auto_crit_target(conditions: ConditionsMap, *, melee: bool) -> bool:
    """Melee hits against paralyzed/unconscious targets are auto-crits."""
    if not melee:
        return False
    return bool(conditions.keys() & _AUTO_CRIT_MELEE)


# ---------------------------------------------------------------------------
# Convenience API — one function per derived stat
# ---------------------------------------------------------------------------


def effective_speed(creature: Creature) -> int:
    """Compute effective movement speed after all modifiers."""
    mods = collect_self_modifiers(creature)
    return compute_stat(creature.speed, mods, StatType.SPEED)


def effective_ac(creature: Creature) -> int:
    """Compute effective AC after all modifiers.

    Characters: armor base + DEX (capped by armor type) + shield + modifiers.
    Unarmored Characters: max(creature.ac, 10 + DEX) for backwards compat.
    Monsters (plain Creature): stat-block AC as-is (DEX already baked in).
    """
    dex_mod = creature.ability_scores.modifier(Ability.DEX)

    if isinstance(creature, Character) and creature.equipped_armor and creature.equipped_armor.armor_def:
        armor = creature.equipped_armor.armor_def
        dex_bonus = min(dex_mod, armor.max_dex_bonus) if armor.max_dex_bonus > 0 else 0
        base = armor.base_ac + dex_bonus
    elif isinstance(creature, Character):
        base = max(creature.ac, 10 + dex_mod)
    else:
        base = creature.ac

    if isinstance(creature, Character) and creature.equipped_shield and creature.equipped_shield.shield_def:
        base += creature.equipped_shield.shield_def.ac_bonus

    mods = collect_self_modifiers(creature)
    return compute_stat(base, mods, StatType.AC)


def attack_modifiers(attacker: Creature, target: Creature, *, melee: bool) -> AttackModifiers:
    """Compute all parameters for an attack roll.

    Collects modifiers from both attacker (self) and target (defense),
    computes flat modifier, dice bonuses, advantage/disadvantage, auto-crit.
    """
    attacker_mods = collect_self_modifiers(attacker)
    target_defense_mods = collect_defense_modifiers(target)

    # Flat modifier: ability + proficiency + weapon magic + flat bonuses from conditions
    attack = get_weapon_attack(attacker)
    ability_mod = attacker.ability_scores.modifier(attack.ability)

    # Proficiency bonus: Characters check class/weapon proficiency; plain Creatures
    # (monsters) are proficient with their natural attacks.
    prof = 0
    if isinstance(attacker, Character):
        weapon = attacker.equipped_weapon
        if weapon and weapon.weapon_def and is_proficient_with_weapon(attacker.char_class, weapon.weapon_def):
            prof = proficiency_bonus(attacker.level)
        elif not weapon and not attacker.attacks:
            # Unarmed strike — all characters are proficient
            prof = proficiency_bonus(attacker.level)
    elif attacker.attacks:
        # Non-Character creatures are proficient with their own attacks
        prof = 2

    base_mod = ability_mod + prof
    flat_mod = compute_stat(base_mod, attacker_mods, StatType.ATTACK_ROLL)

    # Build roll component breakdown
    ability_source = attack.ability.value  # "str", "dex", etc.
    roll_components: list[RollComponent] = [RollComponent(source=ability_source, value=ability_mod)]
    if prof:
        roll_components.append(RollComponent(source="proficiency", value=prof))
    for m in attacker_mods:
        if m.stat == StatType.ATTACK_ROLL and m.op == ModifierOp.ADD and m.value:
            roll_components.append(RollComponent(source=m.source, value=m.value))

    # Damage bonus: ability modifier + Fighting Style bonuses
    # D&D 5e PHB p.196: "You add your ability modifier to the damage"
    dmg_bonus = ability_mod
    dmg_components: list[RollComponent] = []
    if ability_mod:
        dmg_components.append(RollComponent(source=ability_source, value=ability_mod))

    # Class-feature-driven attack contributions (fighting styles, etc.)
    gwf_reroll = False
    if isinstance(attacker, Character):
        for feature in attacker.class_features:
            contribution = feature.collect_attack_modifiers(attacker, melee=melee)
            dmg_bonus += contribution.damage_bonus
            dmg_components.extend(contribution.damage_components)
            if contribution.gwf_reroll:
                gwf_reroll = True

    # Dice bonuses (Bless +1d4, etc.) — unresolved, rolled later by combat_manager
    dice = collect_dice_bonuses(attacker_mods, StatType.ATTACK_ROLL)
    dice_roll_components = tuple(
        RollComponent(source=m.source, value=0, dice=m.dice)
        for m in attacker_mods
        if m.stat == StatType.ATTACK_ROLL and m.op == ModifierOp.ADD and m.dice
    )

    # Advantage/disadvantage: merge attacker self + target defense
    all_adv_mods = [m for m in attacker_mods if m.stat == StatType.ATTACK_ROLL]
    all_adv_mods.extend(m for m in target_defense_mods if m.stat == StatType.ATTACK_ROLL)
    adv, dis = resolve_advantage(all_adv_mods, StatType.ATTACK_ROLL, melee=melee)

    return AttackModifiers(
        modifier=flat_mod,
        damage_bonus=dmg_bonus,
        dice_bonuses=dice,
        advantage=adv,
        disadvantage=dis,
        force_crit=is_auto_crit_target(target.conditions, melee=melee),
        target_ac=effective_ac(target),
        gwf_reroll=gwf_reroll,
        roll_components=tuple(roll_components) + dice_roll_components,
        damage_components=tuple(dmg_components),
    )
