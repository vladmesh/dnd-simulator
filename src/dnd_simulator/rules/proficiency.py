"""D&D 5e proficiency system — bonus calculation and weapon/armor proficiency checks."""

from __future__ import annotations

from dnd_simulator.core.character import CharClass
from dnd_simulator.core.items import ArmorCategory, ArmorDef, WeaponCategory, WeaponDef

# ---------------------------------------------------------------------------
# Class → weapon category proficiencies
# ---------------------------------------------------------------------------

_CLASS_WEAPON_CATEGORIES: dict[CharClass, frozenset[WeaponCategory]] = {
    CharClass.FIGHTER: frozenset({WeaponCategory.SIMPLE, WeaponCategory.MARTIAL}),
    CharClass.PALADIN: frozenset({WeaponCategory.SIMPLE, WeaponCategory.MARTIAL}),
    CharClass.RANGER: frozenset({WeaponCategory.SIMPLE, WeaponCategory.MARTIAL}),
    CharClass.BARBARIAN: frozenset({WeaponCategory.SIMPLE, WeaponCategory.MARTIAL}),
    CharClass.ROGUE: frozenset({WeaponCategory.SIMPLE}),
    CharClass.BARD: frozenset({WeaponCategory.SIMPLE}),
    CharClass.CLERIC: frozenset({WeaponCategory.SIMPLE}),
    CharClass.DRUID: frozenset({WeaponCategory.SIMPLE}),
    CharClass.MONK: frozenset({WeaponCategory.SIMPLE}),
    CharClass.WARLOCK: frozenset({WeaponCategory.SIMPLE}),
    CharClass.WIZARD: frozenset({WeaponCategory.SIMPLE}),
    CharClass.SORCERER: frozenset({WeaponCategory.SIMPLE}),
    CharClass.COMMONER: frozenset({WeaponCategory.SIMPLE}),
}

# ---------------------------------------------------------------------------
# Class → specific weapon_id proficiencies (beyond category)
# ---------------------------------------------------------------------------

_CLASS_SPECIFIC_WEAPONS: dict[CharClass, frozenset[str]] = {
    CharClass.ROGUE: frozenset({"rapier", "shortsword", "longsword", "hand_crossbow"}),
    CharClass.BARD: frozenset({"longsword", "rapier", "hand_crossbow"}),
}

# ---------------------------------------------------------------------------
# Class → armor category proficiencies
# ---------------------------------------------------------------------------

_CLASS_ARMOR_CATEGORIES: dict[CharClass, frozenset[ArmorCategory]] = {
    CharClass.FIGHTER: frozenset({ArmorCategory.LIGHT, ArmorCategory.MEDIUM, ArmorCategory.HEAVY}),
    CharClass.PALADIN: frozenset({ArmorCategory.LIGHT, ArmorCategory.MEDIUM, ArmorCategory.HEAVY}),
    CharClass.RANGER: frozenset({ArmorCategory.LIGHT, ArmorCategory.MEDIUM}),
    CharClass.BARBARIAN: frozenset({ArmorCategory.LIGHT, ArmorCategory.MEDIUM}),
    CharClass.CLERIC: frozenset({ArmorCategory.LIGHT, ArmorCategory.MEDIUM}),
    CharClass.BARD: frozenset({ArmorCategory.LIGHT}),
    CharClass.ROGUE: frozenset({ArmorCategory.LIGHT}),
    CharClass.WARLOCK: frozenset({ArmorCategory.LIGHT}),
    CharClass.DRUID: frozenset({ArmorCategory.LIGHT, ArmorCategory.MEDIUM}),
    CharClass.MONK: frozenset(),
    CharClass.WIZARD: frozenset(),
    CharClass.SORCERER: frozenset(),
    CharClass.COMMONER: frozenset(),
}

# ---------------------------------------------------------------------------
# Class → shield proficiency
# ---------------------------------------------------------------------------

_SHIELD_PROFICIENT: frozenset[CharClass] = frozenset(
    {
        CharClass.FIGHTER,
        CharClass.PALADIN,
        CharClass.RANGER,
        CharClass.CLERIC,
        CharClass.DRUID,
        CharClass.BARBARIAN,
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def proficiency_bonus(level: int) -> int:
    """D&D 5e proficiency bonus by character level."""
    return 2 + (level - 1) // 4


def is_proficient_with_weapon(char_class: CharClass, weapon: WeaponDef) -> bool:
    """Check if a class grants proficiency with a specific weapon."""
    categories = _CLASS_WEAPON_CATEGORIES.get(char_class, frozenset())
    if weapon.category in categories:
        return True
    specific = _CLASS_SPECIFIC_WEAPONS.get(char_class, frozenset())
    return weapon.weapon_id in specific


def is_proficient_with_armor(char_class: CharClass, armor: ArmorDef) -> bool:
    """Check if a class grants proficiency with an armor category."""
    categories = _CLASS_ARMOR_CATEGORIES.get(char_class, frozenset())
    return armor.category in categories


def is_proficient_with_shield(char_class: CharClass) -> bool:
    """Check if a class grants shield proficiency."""
    return char_class in _SHIELD_PROFICIENT
