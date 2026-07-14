"""Tests for multi-damage weapons (sprint 015, phase 4, task 1).

Proves the full chain: WeaponDef with multiple DamageComponents →
resolve_attack rolls each independently → build_damage_components
serializes with correct types → perception formats all types in text →
catalog loading preserves multi-damage structure.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import yaml

from dnd_simulator.core.character import (
    Ability,
    Attack,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.events import DamageComponentPayload
from dnd_simulator.core.modifiers import RollComponent
from dnd_simulator.core.rolls import DiceResult, DieRoll
from dnd_simulator.rules.combat import AttackResult, DamageResult, ExtraDamage, resolve_attack
from dnd_simulator.rules.handlers.attack_resolution import build_damage_components

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flaming_longsword() -> Attack:
    """Flaming longsword: 1d8 slashing + 1d6 fire."""
    return Attack(
        name="flaming_longsword",
        ability=Ability.STR,
        damage=(
            DamageComponent("1d8", DamageType.SLASHING),
            DamageComponent("1d6", DamageType.FIRE),
        ),
    )


def _rng_returning(*values: int) -> random.Random:
    """RNG that yields values in sequence."""
    rng = random.Random()
    seq = list(values)
    idx = [0]

    def _next(a: int, b: int) -> int:
        val = seq[idx[0] % len(seq)]
        idx[0] += 1
        return val

    rng.randint = _next  # type: ignore[assignment]
    return rng


# ---------------------------------------------------------------------------
# 1. Multi-damage weapon resolution (non-crit)
# ---------------------------------------------------------------------------


class TestMultiDamageResolution:
    def test_non_crit_hit_produces_two_damage_entries(self) -> None:
        """Flaming longsword hit (no crit) produces exactly 2 DamageResults:
        one slashing (1d8) and one fire (1d6), each with source='weapon'."""
        # d20=15 (hit, not crit), 1d8=6, 1d6=4
        rng = _rng_returning(15, 6, 4)
        result = resolve_attack(modifier=5, ac=10, attack=_flaming_longsword(), rng=rng)
        assert result.hit is True
        assert result.critical is False
        assert len(result.damage) == 2

        slashing = result.damage[0]
        fire = result.damage[1]

        assert slashing.type == DamageType.SLASHING
        assert slashing.source == "weapon"
        assert slashing.dice == "1d8"
        assert slashing.amount == 6

        assert fire.type == DamageType.FIRE
        assert fire.source == "weapon"
        assert fire.dice == "1d6"
        assert fire.amount == 4

        assert result.total_damage == 10  # 6 + 4

    def test_miss_produces_no_damage_entries(self) -> None:
        """Multi-damage weapon miss produces empty damage tuple."""
        rng = _rng_returning(1)  # nat 1 = auto miss
        result = resolve_attack(modifier=10, ac=5, attack=_flaming_longsword(), rng=rng)
        assert result.hit is False
        assert result.damage == ()
        assert result.total_damage == 0


# ---------------------------------------------------------------------------
# 2. Multi-damage critical hit
# ---------------------------------------------------------------------------


class TestMultiDamageCrit:
    def test_crit_produces_four_damage_entries(self) -> None:
        """Flaming longsword crit: base slashing, crit slashing, base fire, crit fire."""
        # d20=20 (nat crit), base 1d8=5, crit 1d8=3, base 1d6=4, crit 1d6=2
        rng = _rng_returning(20, 5, 3, 4, 2)
        result = resolve_attack(modifier=3, ac=10, attack=_flaming_longsword(), rng=rng)
        assert result.hit is True
        assert result.critical is True
        assert len(result.damage) == 4

        sources = [(d.source, d.type) for d in result.damage]
        assert sources == [
            ("weapon", DamageType.SLASHING),
            ("weapon_crit", DamageType.SLASHING),
            ("weapon", DamageType.FIRE),
            ("weapon_crit", DamageType.FIRE),
        ]

        # total = 5 + 3 + 4 + 2 = 14
        assert result.total_damage == 14


# ---------------------------------------------------------------------------
# 3. Multi-damage + flat bonus (build_damage_components)
# ---------------------------------------------------------------------------


class TestMultiDamageFlatBonus:
    def test_flat_bonus_gets_primary_damage_type(self) -> None:
        """Flat damage bonuses (STR mod, Dueling) get type from first weapon component (slashing),
        not from fire or any other secondary component."""
        dice_result_slash = DiceResult(expression="1d8", dice=(DieRoll(sides=8, result=6),), flat=0, total=6)
        dice_result_fire = DiceResult(expression="1d6", dice=(DieRoll(sides=6, result=4),), flat=0, total=4)
        attack_result = AttackResult(
            hit=True,
            critical=False,
            attack_check=_dummy_check(),
            damage=(
                DamageResult(
                    amount=6, type=DamageType.SLASHING, source="weapon", dice="1d8", dice_result=dice_result_slash
                ),
                DamageResult(amount=4, type=DamageType.FIRE, source="weapon", dice="1d6", dice_result=dice_result_fire),
            ),
            total_damage=14,  # 6 + 4 + 4 (STR)
        )

        damage_comps = (RollComponent(source="ability", value=4, dice=""),)
        components = build_damage_components(attack_result, damage_comps)

        assert len(components) == 3  # slashing weapon, fire weapon, ability flat
        # Flat bonus should have type = slashing (from first weapon component)
        ability_comp = [c for c in components if c.source == "ability"]
        assert len(ability_comp) == 1
        assert ability_comp[0].type == "slashing"
        assert ability_comp[0].amount == 4
        assert ability_comp[0].dice == ""

        # Weapon components keep their own types
        weapon_comps = [c for c in components if c.source == "weapon"]
        assert len(weapon_comps) == 2
        assert weapon_comps[0].type == "slashing"
        assert weapon_comps[1].type == "fire"


# ---------------------------------------------------------------------------
# 4. Multi-damage + extra_damage (Smite on flaming weapon)
# ---------------------------------------------------------------------------


class TestMultiDamageWithExtraDamage:
    def test_flaming_longsword_plus_smite(self) -> None:
        """Flaming longsword hit + Divine Smite = 3 damage types:
        slashing (weapon), fire (weapon), radiant (divine_smite)."""
        # d20=15 (hit, no crit), 1d8=6, 1d6=4, smite 2d8=5+3=8
        rng = _rng_returning(15, 6, 4, 5, 3)
        result = resolve_attack(
            modifier=3,
            ac=10,
            attack=_flaming_longsword(),
            extra_damage=(ExtraDamage(dice="2d8", type=DamageType.RADIANT, source="divine_smite"),),
            rng=rng,
        )
        assert result.hit is True
        assert len(result.damage) == 3

        types_and_sources = [(d.type, d.source) for d in result.damage]
        assert types_and_sources == [
            (DamageType.SLASHING, "weapon"),
            (DamageType.FIRE, "weapon"),
            (DamageType.RADIANT, "divine_smite"),
        ]

        # total = 6 + 4 + 8 = 18
        assert result.total_damage == 18

    def test_flaming_longsword_smite_crit(self) -> None:
        """Flaming longsword crit + Smite = 6 damage entries (base + crit for each)."""
        # d20=20, base 1d8=5, crit 1d8=3, base 1d6=4, crit 1d6=2, smite 2d8=6+4, smite_crit 2d8=3+2
        rng = _rng_returning(20, 5, 3, 4, 2, 6, 4, 3, 2)
        result = resolve_attack(
            modifier=3,
            ac=10,
            attack=_flaming_longsword(),
            extra_damage=(ExtraDamage(dice="2d8", type=DamageType.RADIANT, source="divine_smite"),),
            rng=rng,
        )
        assert result.critical is True
        assert len(result.damage) == 6

        sources = [d.source for d in result.damage]
        assert sources == [
            "weapon",
            "weapon_crit",  # slashing
            "weapon",
            "weapon_crit",  # fire
            "divine_smite",
            "divine_smite_crit",  # radiant
        ]

        types = [d.type for d in result.damage]
        assert types == [
            DamageType.SLASHING,
            DamageType.SLASHING,
            DamageType.FIRE,
            DamageType.FIRE,
            DamageType.RADIANT,
            DamageType.RADIANT,
        ]


# ---------------------------------------------------------------------------
# 5. Perception formatting with multi-damage
# ---------------------------------------------------------------------------


class TestMultiDamagePerception:
    def test_format_damage_shows_both_types(self) -> None:
        """_format_damage with 2 weapon damage components shows both types in text."""
        from dnd_simulator.layers.entities.perception import _format_damage

        components = (
            DamageComponentPayload("weapon", "1d8", (), 6, "slashing"),
            DamageComponentPayload("weapon", "1d6", (), 4, "fire"),
        )
        result = _format_damage(10, components, critical=False)
        assert "10 damage" in result
        assert "1d8" in result
        assert "slashing" in result
        assert "1d6" in result
        assert "fire" in result

    def test_format_damage_multi_plus_flat_bonus(self) -> None:
        """Multi-damage with flat bonus shows all components."""
        from dnd_simulator.layers.entities.perception import _format_damage

        components = (
            DamageComponentPayload("weapon", "1d8", (), 6, "slashing"),
            DamageComponentPayload("weapon", "1d6", (), 4, "fire"),
            DamageComponentPayload("ability", "", (), 4, "slashing"),
        )
        result = _format_damage(14, components, critical=False)
        assert "14 damage" in result
        assert "1d8" in result
        assert "1d6" in result
        assert "+4" in result

    def test_format_damage_multi_plus_smite(self) -> None:
        """Multi-damage weapon + smite shows all three sources."""
        from dnd_simulator.layers.entities.perception import _format_damage

        components = (
            DamageComponentPayload("weapon", "1d8", (), 6, "slashing"),
            DamageComponentPayload("weapon", "1d6", (), 4, "fire"),
            DamageComponentPayload("divine_smite", "2d8", (), 8, "radiant"),
        )
        result = _format_damage(18, components, critical=False)
        assert "18 damage" in result
        assert "1d8 slashing" in result
        assert "1d6 fire" in result
        assert "2d8 divine_smite" in result


# ---------------------------------------------------------------------------
# 6. Catalog loading for multi-damage weapon
# ---------------------------------------------------------------------------


class TestMultiDamageCatalogLoading:
    def test_load_flaming_longsword_from_yaml(self, tmp_path: Path) -> None:
        """YAML weapon with 2 damage entries loads into WeaponDef with 2 DamageComponents."""
        from dnd_simulator.content_loader.catalogs import load_catalog
        from dnd_simulator.content_loader.schemas import ItemContent

        catalog_dir = tmp_path / "items"
        catalog_dir.mkdir()

        weapon_data: dict[str, Any] = {
            "name": "Flaming Longsword",
            "type": "weapon",
            "weapon_id": "flaming_longsword",
            "category": "martial",
            "attack_name": "flaming slash",
            "damage": [
                {"dice": "1d8", "type": "slashing"},
                {"dice": "1d6", "type": "fire"},
            ],
            "modifier": 1,
            "is_magic": True,
        }
        with (catalog_dir / "flaming_longsword.yaml").open("w") as f:
            yaml.dump(weapon_data, f)

        catalog = load_catalog(catalog_dir, ItemContent)
        assert "flaming_longsword" in catalog

        from dnd_simulator.content_loader.items import parse_items

        items = parse_items([{"ref": "flaming_longsword"}], item_catalog=catalog)
        assert len(items) == 1
        item = items[0]
        assert item.weapon_def is not None
        assert len(item.weapon_def.damage) == 2
        assert item.weapon_def.damage[0] == DamageComponent("1d8", DamageType.SLASHING)
        assert item.weapon_def.damage[1] == DamageComponent("1d6", DamageType.FIRE)
        assert item.weapon_def.modifier == 1
        assert item.weapon_def.is_magic is True

    def test_load_frost_dagger_from_yaml(self, tmp_path: Path) -> None:
        """Frost dagger: 1d4 piercing + 1d4 cold, finesse + light."""
        from dnd_simulator.content_loader.catalogs import load_catalog
        from dnd_simulator.content_loader.schemas import ItemContent

        catalog_dir = tmp_path / "items"
        catalog_dir.mkdir()

        weapon_data: dict[str, Any] = {
            "name": "Frost Dagger",
            "type": "weapon",
            "weapon_id": "frost_dagger",
            "category": "simple",
            "attack_name": "frost stab",
            "damage": [
                {"dice": "1d4", "type": "piercing"},
                {"dice": "1d4", "type": "cold"},
            ],
            "ability": "dex",
            "modifier": 1,
            "is_magic": True,
            "is_finesse": True,
            "is_light": True,
        }
        with (catalog_dir / "frost_dagger.yaml").open("w") as f:
            yaml.dump(weapon_data, f)

        catalog = load_catalog(catalog_dir, ItemContent)
        from dnd_simulator.content_loader.items import parse_items

        items = parse_items([{"ref": "frost_dagger"}], item_catalog=catalog)
        item = items[0]
        assert item.weapon_def is not None
        assert len(item.weapon_def.damage) == 2
        assert item.weapon_def.damage[0].type == DamageType.PIERCING
        assert item.weapon_def.damage[1].type == DamageType.COLD
        assert item.weapon_def.is_finesse is True
        assert item.weapon_def.is_light is True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dummy_check() -> Any:
    """Minimal CheckResult for build_damage_components tests."""
    from dnd_simulator.core.rolls import D20Result

    die = DieRoll(sides=20, result=15)
    d20 = D20Result(die=die, alt=None, advantage=False, disadvantage=False)
    from dnd_simulator.rules.checks import CheckResult

    return CheckResult(success=True, roll=15, total=20, dc=10, critical=False, d20=d20)
