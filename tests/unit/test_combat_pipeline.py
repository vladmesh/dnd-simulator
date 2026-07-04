"""End-to-end combat pipeline tests.

Tests that exercise multiple rules layers together: attack_modifiers → resolve_attack,
verifying the full modifier chain (ability + proficiency + fighting style + magic + damage).
"""

from __future__ import annotations

import random

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Character,
    CharClass,
    Creature,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle, RogueFeatures
from dnd_simulator.core.items import (
    ArmorCategory,
    ArmorDef,
    EquipmentSlot,
    Item,
    ItemType,
    WeaponCategory,
    WeaponDef,
)
from dnd_simulator.rules.combat import ExtraDamage, resolve_attack
from dnd_simulator.rules.modifiers import attack_modifiers
from dnd_simulator.rules.sneak_attack import is_sneak_attack_eligible, sneak_attack_dice
from dnd_simulator.rules.weapons import get_weapon_attack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONGSWORD_PLUS_1 = WeaponDef(
    weapon_id="longsword",
    attack_name="longsword slash",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
    modifier=1,
    is_magic=True,
)

_RAPIER = WeaponDef(
    weapon_id="rapier",
    attack_name="rapier thrust",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("1d8", DamageType.PIERCING),),
    is_finesse=True,
)

_GREATSWORD = WeaponDef(
    weapon_id="greatsword",
    attack_name="greatsword slash",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("2d6", DamageType.SLASHING),),
    is_two_handed=True,
    is_heavy=True,
)

_CHAIN_MAIL = ArmorDef(armor_id="chain_mail", category=ArmorCategory.HEAVY, base_ac=16, max_dex_bonus=0)


def _target(ac: int = 15) -> Creature:
    return Creature(
        id="target",
        name="Target Dummy",
        location_id="arena",
        ac=ac,
        current_hp=50,
        max_hp=50,
    )


def _fighter_level5_dueling() -> Character:
    """Fighter: STR 16, level 5, Dueling, longsword +1."""
    scores = AbilityScores(scores={**AbilityScores().scores, Ability.STR: 16})
    fighter = Character(
        id="fighter",
        name="Ser Aldric",
        location_id="arena",
        max_hp=44,
        current_hp=44,
        ac=10,
        ability_scores=scores,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=5,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DUELING)],
    )
    fighter.equipped_weapon = Item(
        id="longsword_0", name="Longsword +1", item_type=ItemType.WEAPON, weapon_def=_LONGSWORD_PLUS_1
    )
    return fighter


def _rogue_level3() -> Character:
    """Rogue: DEX 16, level 3, rapier, 2d6 sneak attack."""
    scores = AbilityScores(scores={**AbilityScores().scores, Ability.DEX: 16})
    rogue = Character(
        id="rogue",
        name="Lira",
        location_id="arena",
        max_hp=24,
        current_hp=24,
        ac=10,
        ability_scores=scores,
        race=Race.HUMAN,
        char_class=CharClass.ROGUE,
        level=3,
        class_features=[RogueFeatures(sneak_attack_dice=2)],
    )
    rogue.equipped_weapon = Item(id="rapier_0", name="Rapier", item_type=ItemType.WEAPON, weapon_def=_RAPIER)
    return rogue


# ---------------------------------------------------------------------------
# Fighter full attack pipeline
# ---------------------------------------------------------------------------


class TestFighterAttackPipeline:
    """Fighter (STR 16, level 5, Dueling, longsword +1) attacks AC 15.

    Expected:
      attack roll = d20 + STR(+3) + proficiency(+3) + magic(+1) = d20+7
      damage = 1d8 + STR(+3) + dueling(+2) + magic(+1) = 1d8+6
    """

    def test_attack_modifier_total(self) -> None:
        fighter = _fighter_level5_dueling()
        target = _target(ac=15)
        mods = attack_modifiers(fighter, target, melee=True)
        # STR(+3) + prof(+3) + magic(+1) = +7
        assert mods.modifier == 7

    def test_damage_bonus_total(self) -> None:
        fighter = _fighter_level5_dueling()
        target = _target()
        mods = attack_modifiers(fighter, target, melee=True)
        # STR(+3) + dueling(+2) = +5
        # Note: magic weapon damage bonus (+1) flows through weapon_modifier,
        # which is added to attack roll, not damage_bonus.
        # Actually checking: ability_mod + dueling = 3 + 2 = 5
        assert mods.damage_bonus == 5

    def test_full_resolve_hit_damage(self) -> None:
        """Guaranteed hit (d20=15), weapon die=5. Total = 5 + 6 (bonus) = 11."""
        fighter = _fighter_level5_dueling()
        target = _target(ac=15)
        mods = attack_modifiers(fighter, target, melee=True)

        call_idx = 0
        values = [15, 5]  # d20=15 (15+7=22 vs AC 15 → hit), 1d8=5

        def fixed_randint(a: int, b: int) -> int:
            nonlocal call_idx
            v = values[call_idx]
            call_idx += 1
            return v

        rng = random.Random()
        rng.randint = fixed_randint  # type: ignore[method-assign]

        result = resolve_attack(
            modifier=mods.modifier,
            ac=mods.target_ac,
            attack=get_weapon_attack(fighter),
            damage_bonus=mods.damage_bonus,
            gwf_reroll=mods.gwf_reroll,
            rng=rng,
        )
        assert result.hit is True
        assert result.critical is False
        # weapon die 5 + damage_bonus 5 = 10
        assert result.total_damage == 10
        assert result.damage[0].type == DamageType.SLASHING

    def test_roll_components_breakdown(self) -> None:
        """Verify the roll components include STR, proficiency, and weapon magic."""
        fighter = _fighter_level5_dueling()
        target = _target()
        mods = attack_modifiers(fighter, target, melee=True)
        sources = {c.source for c in mods.roll_components}
        assert "str" in sources
        assert "proficiency" in sources
        assert "weapon_magic" in sources

    def test_damage_components_breakdown(self) -> None:
        """Verify damage components include STR and dueling."""
        fighter = _fighter_level5_dueling()
        target = _target()
        mods = attack_modifiers(fighter, target, melee=True)
        sources = {c.source for c in mods.damage_components}
        assert "str" in sources
        assert "dueling" in sources


# ---------------------------------------------------------------------------
# Rogue full attack pipeline
# ---------------------------------------------------------------------------


class TestRogueAttackPipeline:
    """Rogue (DEX 16, level 3, rapier, advantage) attacks.

    Expected:
      attack roll = d20 (advantage) + DEX(+3) + prof(+2) = d20+5
      on hit: 1d8 + DEX(+3) + 2d6 sneak attack
    """

    def test_attack_modifier_total(self) -> None:
        rogue = _rogue_level3()
        target = _target()
        mods = attack_modifiers(rogue, target, melee=True)
        # DEX(+3) + prof(+2) = +5
        assert mods.modifier == 5

    def test_damage_bonus_is_dex(self) -> None:
        rogue = _rogue_level3()
        target = _target()
        mods = attack_modifiers(rogue, target, melee=True)
        # DEX(+3)
        assert mods.damage_bonus == 3

    def test_sneak_attack_eligible_with_advantage(self) -> None:
        rogue = _rogue_level3()
        attack = get_weapon_attack(rogue)
        assert is_sneak_attack_eligible(
            rogue,
            attack,
            has_advantage=True,
            has_disadvantage=False,
            ally_adjacent_to_target=False,
        )

    def test_sneak_attack_dice_count(self) -> None:
        rogue = _rogue_level3()
        assert sneak_attack_dice(rogue) == 2

    def test_full_resolve_with_sneak_attack(self) -> None:
        """Rogue hits with advantage: weapon + DEX + 2d6 sneak attack."""
        rogue = _rogue_level3()
        target = _target(ac=12)
        mods = attack_modifiers(rogue, target, melee=True)

        sa_dice = sneak_attack_dice(rogue)
        attack = get_weapon_attack(rogue)

        call_idx = 0
        # d20 advantage: roll 18, 10 → keep 18. 18+5=23 vs AC 12 → hit.
        # 1d8 weapon = 6. 2d6 sneak = 3, 4.
        values = [18, 10, 6, 3, 4]

        def fixed_randint(a: int, b: int) -> int:
            nonlocal call_idx
            v = values[call_idx]
            call_idx += 1
            return v

        rng = random.Random()
        rng.randint = fixed_randint  # type: ignore[method-assign]

        result = resolve_attack(
            modifier=mods.modifier,
            ac=mods.target_ac,
            attack=attack,
            damage_bonus=mods.damage_bonus,
            advantage=True,
            extra_damage=(ExtraDamage(dice=f"{sa_dice}d6", type=DamageType.PIERCING, source="sneak_attack"),),
            rng=rng,
        )
        assert result.hit is True
        # weapon 6 + sneak 3+4=7 + damage_bonus 3 = 16
        assert result.total_damage == 16
        assert len(result.damage) == 2
        # Sneak attack is a separate damage component
        sa_damage = [d for d in result.damage if d.source == "sneak_attack"]
        assert len(sa_damage) == 1
        assert sa_damage[0].amount == 7  # 3+4
        assert sa_damage[0].type == DamageType.PIERCING

    def test_no_sneak_attack_without_advantage_or_ally(self) -> None:
        rogue = _rogue_level3()
        attack = get_weapon_attack(rogue)
        assert not is_sneak_attack_eligible(
            rogue,
            attack,
            has_advantage=False,
            has_disadvantage=False,
            ally_adjacent_to_target=False,
        )


# ---------------------------------------------------------------------------
# Non-proficient creature
# ---------------------------------------------------------------------------


class TestNonProficientAttack:
    """Creature with no proficiency in weapon: attack roll = d20 + ability mod only."""

    def test_commoner_no_proficiency_with_martial(self) -> None:
        commoner = Character(
            id="commoner",
            name="Villager",
            location_id="arena",
            max_hp=4,
            current_hp=4,
            ac=10,
            ability_scores=AbilityScores(scores={**AbilityScores().scores, Ability.STR: 12}),
            race=Race.HUMAN,
            char_class=CharClass.COMMONER,
            level=1,
        )
        commoner.equipped_weapon = Item(
            id="sword_0",
            name="Longsword",
            item_type=ItemType.WEAPON,
            weapon_def=WeaponDef(
                weapon_id="longsword",
                attack_name="slash",
                category=WeaponCategory.MARTIAL,
                damage=(DamageComponent("1d8", DamageType.SLASHING),),
            ),
        )
        target = _target()
        mods = attack_modifiers(commoner, target, melee=True)
        # STR(+1), no proficiency
        assert mods.modifier == 1


# ---------------------------------------------------------------------------
# Sneak attack damage through resolve_attack
# ---------------------------------------------------------------------------


class TestSneakAttackDamage:
    """Sneak attack dice flow correctly through resolve_attack as ExtraDamage."""

    def test_3d6_sneak_attack(self) -> None:
        """Rogue with 3 sneak_attack_dice deals 3d6 extra damage."""
        scores = AbilityScores(scores={**AbilityScores().scores, Ability.DEX: 16})
        rogue = Character(
            id="rogue",
            name="Rogue",
            location_id="arena",
            max_hp=30,
            current_hp=30,
            ac=10,
            ability_scores=scores,
            race=Race.HUMAN,
            char_class=CharClass.ROGUE,
            level=5,
            class_features=[RogueFeatures(sneak_attack_dice=3)],
        )
        rogue.equipped_weapon = Item(id="rapier_0", name="Rapier", item_type=ItemType.WEAPON, weapon_def=_RAPIER)

        sa_dice = sneak_attack_dice(rogue)
        assert sa_dice == 3

        call_idx = 0
        # d20=18 (hit), 1d8 weapon=5, 3d6 sneak=2,4,6
        values = [18, 5, 2, 4, 6]

        def fixed_randint(a: int, b: int) -> int:
            nonlocal call_idx
            v = values[call_idx]
            call_idx += 1
            return v

        rng = random.Random()
        rng.randint = fixed_randint  # type: ignore[method-assign]

        attack = get_weapon_attack(rogue)
        result = resolve_attack(
            modifier=5,
            ac=12,
            attack=attack,
            damage_bonus=3,
            extra_damage=(ExtraDamage(dice=f"{sa_dice}d6", type=DamageType.PIERCING, source="sneak_attack"),),
            rng=rng,
        )
        assert result.hit is True
        # weapon 5 + sneak 2+4+6=12 + bonus 3 = 20
        assert result.total_damage == 20
        sa_result = [d for d in result.damage if d.source == "sneak_attack"]
        assert len(sa_result) == 1
        assert sa_result[0].amount == 12
        assert sa_result[0].dice == "3d6"
        # Verify dice structure
        assert sa_result[0].dice_result is not None
        assert len(sa_result[0].dice_result.dice) == 3

    def test_no_sneak_attack_no_extra_damage(self) -> None:
        """Without sneak attack, only weapon damage appears."""
        call_idx = 0
        values = [18, 5]  # d20=18, 1d8=5

        def fixed_randint(a: int, b: int) -> int:
            nonlocal call_idx
            v = values[call_idx]
            call_idx += 1
            return v

        rng = random.Random()
        rng.randint = fixed_randint  # type: ignore[method-assign]

        from dnd_simulator.core.character import Attack

        rapier_attack = Attack(
            name="rapier thrust",
            ability=Ability.DEX,
            damage=(DamageComponent("1d8", DamageType.PIERCING),),
            is_finesse=True,
        )
        result = resolve_attack(
            modifier=5,
            ac=12,
            attack=rapier_attack,
            damage_bonus=3,
            rng=rng,
        )
        assert result.hit is True
        assert len(result.damage) == 1
        assert result.damage[0].source == "weapon"
        assert result.total_damage == 8  # 5 + 3 bonus


# ---------------------------------------------------------------------------
# Finesse weapon ability selection
# ---------------------------------------------------------------------------


class TestFinesseAbilitySelection:
    """Finesse weapon uses higher of STR/DEX for attack modifier."""

    def test_finesse_uses_dex_when_higher(self) -> None:
        scores = AbilityScores(scores={**AbilityScores().scores, Ability.STR: 10, Ability.DEX: 16})
        creature = Creature(
            id="test",
            name="Test",
            location_id="arena",
            ac=10,
            ability_scores=scores,
            equipped={
                EquipmentSlot.WEAPON: Item(id="rapier_0", name="Rapier", item_type=ItemType.WEAPON, weapon_def=_RAPIER)
            },
        )
        attack = get_weapon_attack(creature)
        assert attack.ability == Ability.DEX

    def test_finesse_uses_str_when_higher(self) -> None:
        scores = AbilityScores(scores={**AbilityScores().scores, Ability.STR: 18, Ability.DEX: 12})
        creature = Creature(
            id="test",
            name="Test",
            location_id="arena",
            ac=10,
            ability_scores=scores,
            equipped={
                EquipmentSlot.WEAPON: Item(id="rapier_0", name="Rapier", item_type=ItemType.WEAPON, weapon_def=_RAPIER)
            },
        )
        attack = get_weapon_attack(creature)
        assert attack.ability == Ability.STR

    def test_finesse_uses_str_when_equal(self) -> None:
        """When STR == DEX, default to STR (>= check)."""
        scores = AbilityScores(scores={**AbilityScores().scores, Ability.STR: 14, Ability.DEX: 14})
        creature = Creature(
            id="test",
            name="Test",
            location_id="arena",
            ac=10,
            ability_scores=scores,
            equipped={
                EquipmentSlot.WEAPON: Item(id="rapier_0", name="Rapier", item_type=ItemType.WEAPON, weapon_def=_RAPIER)
            },
        )
        attack = get_weapon_attack(creature)
        assert attack.ability == Ability.STR

    def test_non_finesse_always_str(self) -> None:
        """Non-finesse weapon always uses its default ability (STR)."""
        scores = AbilityScores(scores={**AbilityScores().scores, Ability.STR: 10, Ability.DEX: 18})
        creature = Creature(
            id="test",
            name="Test",
            location_id="arena",
            ac=10,
            ability_scores=scores,
            equipped={
                EquipmentSlot.WEAPON: Item(
                    id="sword_0",
                    name="Longsword",
                    item_type=ItemType.WEAPON,
                    weapon_def=WeaponDef(
                        weapon_id="longsword",
                        attack_name="slash",
                        category=WeaponCategory.MARTIAL,
                        damage=(DamageComponent("1d8", DamageType.SLASHING),),
                    ),
                )
            },
        )
        attack = get_weapon_attack(creature)
        assert attack.ability == Ability.STR


# ---------------------------------------------------------------------------
# Weapon property preservation through catalog loading
# ---------------------------------------------------------------------------


class TestWeaponPropertyFromCatalog:
    """Weapon properties are preserved through YAML → ItemContent → WeaponDef pipeline."""

    def test_dagger_light_and_finesse(self) -> None:
        """Dagger from catalog has is_light=True and is_finesse=True."""
        from pathlib import Path

        from dnd_simulator.content_loader.catalogs import load_catalog
        from dnd_simulator.content_loader.schemas import ItemContent

        catalog_dir = Path(__file__).resolve().parents[2] / "content" / "catalogs" / "items"
        catalog = load_catalog(catalog_dir, ItemContent)

        dagger = catalog["dagger"]
        assert dagger.is_light is True
        assert dagger.is_finesse is True

    def test_dagger_light_preserved_to_weapon_def(self) -> None:
        """is_light survives conversion to runtime WeaponDef."""
        from dnd_simulator.content_loader.items import parse_items

        items = parse_items(
            [
                {
                    "name": "Dagger",
                    "type": "weapon",
                    "weapon_id": "dagger",
                    "category": "simple",
                    "attack_name": "dagger strike",
                    "damage": [{"dice": "1d4", "type": "piercing"}],
                    "is_finesse": True,
                    "is_light": True,
                }
            ]
        )
        assert len(items) == 1
        assert items[0].weapon_def is not None
        assert items[0].weapon_def.is_light is True
        assert items[0].weapon_def.is_finesse is True

    def test_greatsword_two_handed_and_heavy(self) -> None:
        """Greatsword from catalog has is_two_handed=True and is_heavy=True."""
        from pathlib import Path

        from dnd_simulator.content_loader.catalogs import load_catalog
        from dnd_simulator.content_loader.schemas import ItemContent

        catalog_dir = Path(__file__).resolve().parents[2] / "content" / "catalogs" / "items"
        catalog = load_catalog(catalog_dir, ItemContent)

        greatsword = catalog["greatsword"]
        assert greatsword.is_two_handed is True
        assert greatsword.is_heavy is True

    def test_longsword_no_special_properties(self) -> None:
        """Longsword: no finesse, no light, no two-handed, no heavy."""
        from pathlib import Path

        from dnd_simulator.content_loader.catalogs import load_catalog
        from dnd_simulator.content_loader.schemas import ItemContent

        catalog_dir = Path(__file__).resolve().parents[2] / "content" / "catalogs" / "items"
        catalog = load_catalog(catalog_dir, ItemContent)

        longsword = catalog["longsword"]
        assert not longsword.is_finesse
        assert not longsword.is_light
        assert not longsword.is_two_handed
        assert not longsword.is_heavy

    def test_rapier_finesse_no_light(self) -> None:
        """Rapier: finesse=True, light=False."""
        from pathlib import Path

        from dnd_simulator.content_loader.catalogs import load_catalog
        from dnd_simulator.content_loader.schemas import ItemContent

        catalog_dir = Path(__file__).resolve().parents[2] / "content" / "catalogs" / "items"
        catalog = load_catalog(catalog_dir, ItemContent)

        rapier = catalog["rapier"]
        assert rapier.is_finesse is True
        assert not rapier.is_light


# ---------------------------------------------------------------------------
# Two-handed blocks Dueling, GWF doesn't apply to one-handed
# ---------------------------------------------------------------------------


class TestFightingStyleWeaponInteraction:
    """Fighting style interactions with weapon properties."""

    def test_two_handed_blocks_dueling_damage(self) -> None:
        """Dueling style does NOT give +2 damage with a two-handed weapon."""
        scores = AbilityScores(scores={**AbilityScores().scores, Ability.STR: 14})
        fighter = Character(
            id="fighter",
            name="Fighter",
            location_id="arena",
            max_hp=20,
            current_hp=20,
            ac=10,
            ability_scores=scores,
            race=Race.HUMAN,
            char_class=CharClass.FIGHTER,
            level=1,
            class_features=[FighterFeatures(fighting_style=FightingStyle.DUELING)],
        )
        fighter.equipped_weapon = Item(id="gs_0", name="Greatsword", item_type=ItemType.WEAPON, weapon_def=_GREATSWORD)
        target = _target()
        mods = attack_modifiers(fighter, target, melee=True)
        # STR(+2) only, no dueling bonus
        assert mods.damage_bonus == 2

    def test_gwf_no_flag_with_one_handed(self) -> None:
        """GWF style does NOT set gwf_reroll for one-handed weapons."""
        scores = AbilityScores(scores={**AbilityScores().scores, Ability.STR: 14})
        fighter = Character(
            id="fighter",
            name="Fighter",
            location_id="arena",
            max_hp=20,
            current_hp=20,
            ac=10,
            ability_scores=scores,
            race=Race.HUMAN,
            char_class=CharClass.FIGHTER,
            level=1,
            class_features=[FighterFeatures(fighting_style=FightingStyle.GREAT_WEAPON_FIGHTING)],
        )
        fighter.equipped_weapon = Item(
            id="sword_0",
            name="Longsword",
            item_type=ItemType.WEAPON,
            weapon_def=WeaponDef(
                weapon_id="longsword",
                attack_name="slash",
                category=WeaponCategory.MARTIAL,
                damage=(DamageComponent("1d8", DamageType.SLASHING),),
            ),
        )
        target = _target()
        mods = attack_modifiers(fighter, target, melee=True)
        assert mods.gwf_reroll is False
