"""Coverage for shield proficiency penalties and stat-specific advantage resolution."""

import pytest

from dnd_simulator.core.character import Character, CharClass, Creature, Race
from dnd_simulator.core.items import Item, ItemType, ShieldDef
from dnd_simulator.core.modifiers import Modifier, ModifierOp, StatType
from dnd_simulator.rules.modifiers import (
    attack_modifiers,
    collect_self_modifiers,
    effective_ac,
    resolve_advantage,
)


@pytest.mark.parametrize(
    ("char_class", "disadvantage"),
    [(CharClass.FIGHTER, False), (CharClass.ROGUE, True)],
)
def test_shield_proficiency_controls_attack_penalty(char_class: CharClass, disadvantage: bool) -> None:
    character = Character(
        id="test_char",
        name="Test",
        location_id="arena",
        max_hp=20,
        current_hp=20,
        ac=10,
        race=Race.HUMAN,
        char_class=char_class,
        level=1,
    )
    target = Creature(id="target", name="Target", location_id="arena", ac=10)
    character.equipped_shield = Item(
        id="shield_0",
        name="Shield",
        item_type=ItemType.SHIELD,
        shield_def=ShieldDef(shield_id="shield", ac_bonus=2),
    )

    expected_modifiers = (
        [Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="non_proficient_shield")]
        if disadvantage
        else []
    )
    assert collect_self_modifiers(character) == expected_modifiers
    result = attack_modifiers(character, target, melee=True)
    assert (result.advantage, result.disadvantage) == (False, disadvantage)
    assert result.modifier == 2
    assert effective_ac(character) == 12

    character.equipped_shield = None
    assert collect_self_modifiers(character) == []
    assert attack_modifiers(character, target, melee=True).disadvantage is False
    assert effective_ac(character) == 10


@pytest.mark.parametrize(
    ("other_stat", "other_op", "attack_op", "expected"),
    [
        (StatType.AC, ModifierOp.ADVANTAGE, ModifierOp.DISADVANTAGE, (False, True)),
        (StatType.SPEED, ModifierOp.DISADVANTAGE, ModifierOp.ADVANTAGE, (True, False)),
    ],
)
def test_resolve_advantage_ignores_other_stats(
    other_stat: StatType,
    other_op: ModifierOp,
    attack_op: ModifierOp,
    expected: tuple[bool, bool],
) -> None:
    modifiers = [
        Modifier(other_stat, other_op, source="other_stat"),
        Modifier(StatType.ATTACK_ROLL, attack_op, source="attack"),
    ]

    assert resolve_advantage(modifiers, StatType.ATTACK_ROLL) == expected
