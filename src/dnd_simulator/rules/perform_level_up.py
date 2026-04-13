"""Level-up operation: apply the next level to a Character.

Mutates the Character dataclass in place: recomputes max_hp, rebuilds class
feature entries at the new level, merges resource pools (preserving
current_uses for existing pools), and clears the level_up_available flag.

This is an explicit exception to the ``rules/`` purity rule — level-up is
the canonical mutation entry-point for class progression. Character is
already a mutable dataclass (HP, equipment, conditions all mutate during
play), so returning a new instance would be inconsistent with how the rest
of the game treats creature state. The in-place contract is pinned by
``tests/unit/test_rules_perform_level_up_purity.py``.

Validation lives here too — caller supplies class-specific choices via the
``fighting_style`` kwarg.
"""

from __future__ import annotations

from dataclasses import replace

from dnd_simulator.core.character import Ability, Character, CharClass
from dnd_simulator.core.class_features import (
    ClassFeatures,
    FighterFeatures,
    FightingStyle,
    PaladinFeatures,
    RogueFeatures,
)
from dnd_simulator.core.resource import ResourcePool
from dnd_simulator.rules.character_creation import calculate_max_hp
from dnd_simulator.rules.resources import build_class_resource_pools


def perform_level_up(character: Character, *, fighting_style: FightingStyle | None) -> None:
    """Apply the next level to ``character`` in place.

    Mutates the passed instance — callers keep the same ``Character`` object.
    Returns ``None``. This is the only mutation entry-point for level-up;
    see the module docstring for why ``rules/`` purity is waived here.

    Raises ``ValueError`` if ``level_up_available`` is False or the
    ``fighting_style`` argument is incompatible with the class/level transition.
    """
    if not character.level_up_available:
        raise ValueError("No level-up available")

    old_level = character.level
    new_level = old_level + 1

    _validate_fighting_style(character.char_class, old_level, new_level, fighting_style)

    con_mod = character.ability_scores.modifier(Ability.CON)
    new_max_hp = calculate_max_hp(character.char_class, new_level, con_mod)
    hp_delta = new_max_hp - character.max_hp
    character.max_hp = new_max_hp
    character.current_hp += hp_delta

    character.class_features = _rebuild_features(character.class_features, new_level, fighting_style)
    character.resource_pools = _merge_pools(
        character.resource_pools, build_class_resource_pools(character.char_class, new_level)
    )

    character.level = new_level
    character.level_up_available = False


def _validate_fighting_style(
    char_class: CharClass, old_level: int, new_level: int, style: FightingStyle | None
) -> None:
    paladin_l1_to_l2 = char_class == CharClass.PALADIN and old_level == 1 and new_level == 2
    if paladin_l1_to_l2:
        if style is None:
            raise ValueError("Paladin level 2 requires a fighting_style choice")
        return
    if style is not None:
        raise ValueError(f"fighting_style is not applicable for {char_class.value} level {old_level}->{new_level}")


def _rebuild_features(
    features: list[ClassFeatures], new_level: int, paladin_style: FightingStyle | None
) -> list[ClassFeatures]:
    rebuilt: list[ClassFeatures] = []
    for feat in features:
        if isinstance(feat, FighterFeatures | RogueFeatures):
            rebuilt.append(replace(feat, level=new_level))
        elif isinstance(feat, PaladinFeatures):
            if paladin_style is not None:
                rebuilt.append(replace(feat, level=new_level, fighting_style=paladin_style))
            else:
                rebuilt.append(replace(feat, level=new_level))
    return rebuilt


def _merge_pools(existing: list[ResourcePool], target: list[ResourcePool]) -> list[ResourcePool]:
    existing_by_id = {p.id: p for p in existing}
    merged: list[ResourcePool] = []
    for pool in target:
        prior = existing_by_id.get(pool.id)
        if prior is None:
            merged.append(pool)
        else:
            current = min(prior.current_uses, pool.max_uses)
            merged.append(
                ResourcePool(id=pool.id, max_uses=pool.max_uses, current_uses=current, reset_on=pool.reset_on)
            )
    return merged
