"""Tests for Sneak Attack — Rogue core mechanic."""

from __future__ import annotations

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    CharClass,
    Creature,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.class_features import RogueFeatures
from dnd_simulator.core.items import WeaponCategory, WeaponDef
from dnd_simulator.rules.sneak_attack import (
    is_sneak_attack_eligible,
    is_sneak_attack_weapon,
    sneak_attack_dice,
)


def _rogue(*, level: int = 1, sneak_dice: int = 1) -> Character:
    scores = AbilityScores()
    scores[Ability.DEX] = 18  # +4
    return Character(
        id="rogue",
        name="Test Rogue",
        location_id="loc",
        ac=14,
        current_hp=20,
        max_hp=20,
        speed=30,
        ability_scores=scores,
        race=Race.HUMAN,
        char_class=CharClass.ROGUE,
        level=level,
        class_features=[RogueFeatures(sneak_attack_dice=sneak_dice)],
    )


def _fighter() -> Character:
    return Character(
        id="fighter",
        name="Test Fighter",
        location_id="loc",
        ac=16,
        current_hp=30,
        max_hp=30,
        speed=30,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=1,
    )


def _plain_creature() -> Creature:
    return Creature(
        id="goblin",
        name="Goblin",
        location_id="loc",
        ac=12,
        current_hp=10,
        max_hp=10,
        speed=30,
    )


_RAPIER_DEF = WeaponDef(
    weapon_id="rapier",
    attack_name="rapier strike",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("1d8", DamageType.PIERCING),),
    is_finesse=True,
)

_LONGSWORD_DEF = WeaponDef(
    weapon_id="longsword",
    attack_name="longsword strike",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)

_LONGBOW_DEF = WeaponDef(
    weapon_id="longbow",
    attack_name="longbow shot",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("1d8", DamageType.PIERCING),),
    ability=Ability.DEX,
    reach=150,
)


def _rapier_attack() -> Attack:
    return Attack(
        name="rapier strike",
        ability=Ability.DEX,
        damage=(DamageComponent("1d8", DamageType.PIERCING),),
        reach=5,
        is_finesse=True,
    )


def _longsword_attack() -> Attack:
    return Attack(
        name="longsword strike",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
        reach=5,
    )


def _longbow_attack() -> Attack:
    return Attack(
        name="longbow shot",
        ability=Ability.DEX,
        damage=(DamageComponent("1d8", DamageType.PIERCING),),
        reach=150,
    )


# ---------------------------------------------------------------------------
# sneak_attack_dice()
# ---------------------------------------------------------------------------


class TestSneakAttackDice:
    def test_rogue_returns_dice(self) -> None:
        rogue = _rogue(sneak_dice=3)
        assert sneak_attack_dice(rogue) == 3

    def test_rogue_default_1d6(self) -> None:
        rogue = _rogue()
        assert sneak_attack_dice(rogue) == 1

    def test_fighter_returns_zero(self) -> None:
        assert sneak_attack_dice(_fighter()) == 0

    def test_plain_creature_returns_zero(self) -> None:
        assert sneak_attack_dice(_plain_creature()) == 0


# ---------------------------------------------------------------------------
# is_sneak_attack_weapon()
# ---------------------------------------------------------------------------


class TestSneakAttackWeapon:
    def test_finesse_qualifies(self) -> None:
        assert is_sneak_attack_weapon(_rapier_attack()) is True

    def test_ranged_qualifies(self) -> None:
        assert is_sneak_attack_weapon(_longbow_attack()) is True

    def test_non_finesse_melee_does_not_qualify(self) -> None:
        assert is_sneak_attack_weapon(_longsword_attack()) is False


# ---------------------------------------------------------------------------
# is_sneak_attack_eligible()
# ---------------------------------------------------------------------------


class TestSneakAttackEligibility:
    def test_eligible_with_advantage(self) -> None:
        assert (
            is_sneak_attack_eligible(
                _rogue(),
                _rapier_attack(),
                has_advantage=True,
                has_disadvantage=False,
                ally_adjacent_to_target=False,
            )
            is True
        )

    def test_eligible_with_ally_adjacent(self) -> None:
        assert (
            is_sneak_attack_eligible(
                _rogue(),
                _rapier_attack(),
                has_advantage=False,
                has_disadvantage=False,
                ally_adjacent_to_target=True,
            )
            is True
        )

    def test_not_eligible_disadvantage_cancels_advantage(self) -> None:
        """D&D 5e: advantage + disadvantage = flat roll, SA via advantage doesn't trigger."""
        assert (
            is_sneak_attack_eligible(
                _rogue(),
                _rapier_attack(),
                has_advantage=True,
                has_disadvantage=True,
                ally_adjacent_to_target=False,
            )
            is False
        )

    def test_not_eligible_disadvantage_blocks_ally(self) -> None:
        """D&D 5e: disadvantage blocks SA even with ally adjacent."""
        assert (
            is_sneak_attack_eligible(
                _rogue(),
                _rapier_attack(),
                has_advantage=False,
                has_disadvantage=True,
                ally_adjacent_to_target=True,
            )
            is False
        )

    def test_not_eligible_no_advantage_no_ally(self) -> None:
        assert (
            is_sneak_attack_eligible(
                _rogue(),
                _rapier_attack(),
                has_advantage=False,
                has_disadvantage=False,
                ally_adjacent_to_target=False,
            )
            is False
        )

    def test_not_eligible_wrong_weapon(self) -> None:
        """Longsword is not finesse — SA doesn't work."""
        assert (
            is_sneak_attack_eligible(
                _rogue(),
                _longsword_attack(),
                has_advantage=True,
                has_disadvantage=False,
                ally_adjacent_to_target=False,
            )
            is False
        )

    def test_not_eligible_fighter(self) -> None:
        assert (
            is_sneak_attack_eligible(
                _fighter(),
                _rapier_attack(),
                has_advantage=True,
                has_disadvantage=False,
                ally_adjacent_to_target=False,
            )
            is False
        )

    def test_not_eligible_plain_creature(self) -> None:
        assert (
            is_sneak_attack_eligible(
                _plain_creature(),
                _rapier_attack(),
                has_advantage=True,
                has_disadvantage=False,
                ally_adjacent_to_target=False,
            )
            is False
        )

    def test_eligible_ranged_with_advantage(self) -> None:
        assert (
            is_sneak_attack_eligible(
                _rogue(),
                _longbow_attack(),
                has_advantage=True,
                has_disadvantage=False,
                ally_adjacent_to_target=False,
            )
            is True
        )

    def test_ally_adjacent_with_advantage_still_works(self) -> None:
        """Both conditions met — still eligible."""
        assert (
            is_sneak_attack_eligible(
                _rogue(),
                _rapier_attack(),
                has_advantage=True,
                has_disadvantage=False,
                ally_adjacent_to_target=True,
            )
            is True
        )
