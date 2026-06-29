"""Tests for attack & damage breakdown pipeline (sprint 011, phase 0, task 2).

Verifies that structured dice results thread through:
  checks → combat → combat_manager event data → healing events.
"""

from __future__ import annotations

import random

from dnd_simulator.core.character import (
    Ability,
    Attack,
    Character,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.rolls import D20Result, DiceResult, DieRoll
from dnd_simulator.rules.checks import CheckResult, attack_roll
from dnd_simulator.rules.combat import ExtraDamage, resolve_attack
from dnd_simulator.rules.handlers.attack_resolution import build_attack_event, build_damage_components

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rng_returning(*values: int) -> random.Random:
    """RNG that yields values in sequence, cycling if needed."""
    rng = random.Random()
    seq = list(values)
    idx = [0]

    def _next(a: int, b: int) -> int:
        val = seq[idx[0] % len(seq)]
        idx[0] += 1
        return val

    rng.randint = _next  # type: ignore[assignment]
    return rng


def _sword() -> Attack:
    return Attack(
        name="longsword",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )


# ---------------------------------------------------------------------------
# CheckResult with D20Result
# ---------------------------------------------------------------------------


class TestCheckResultD20:
    def test_attack_roll_carries_d20_result(self) -> None:
        """attack_roll() stores the full D20Result on CheckResult.d20."""
        rng = _rng_returning(14)
        result = attack_roll(modifier=5, ac=15, rng=rng)
        assert result.d20 is not None
        assert result.d20.natural == 14
        assert result.d20.alt is None

    def test_attack_roll_advantage_has_alt(self) -> None:
        """With advantage, d20.alt carries the discarded die."""
        # First roll 14, second roll 7 → keeps 14
        rng = _rng_returning(14, 7)
        result = attack_roll(modifier=5, ac=15, advantage=True, rng=rng)
        assert result.d20.alt is not None
        assert result.d20.die.result >= result.d20.alt.result
        assert result.d20.advantage is True

    def test_attack_roll_disadvantage_has_alt(self) -> None:
        """With disadvantage, d20.alt carries the discarded die."""
        rng = _rng_returning(14, 7)
        result = attack_roll(modifier=5, ac=15, disadvantage=True, rng=rng)
        assert result.d20.alt is not None
        assert result.d20.die.result <= result.d20.alt.result
        assert result.d20.disadvantage is True

    def test_attack_roll_straight_no_alt(self) -> None:
        """Straight roll — no alt die."""
        rng = _rng_returning(10)
        result = attack_roll(modifier=0, ac=10, rng=rng)
        assert result.d20.alt is None
        assert result.d20.advantage is False
        assert result.d20.disadvantage is False


# ---------------------------------------------------------------------------
# DamageResult with DiceResult
# ---------------------------------------------------------------------------


class TestDamageResultDiceResult:
    def test_hit_damage_carries_dice_result(self) -> None:
        """On hit, each DamageResult has a dice_result with individual die faces."""
        # d20=15 (hits AC 10 with +5), then damage die
        rng = _rng_returning(15, 6)
        result = resolve_attack(modifier=5, ac=10, attack=_sword(), rng=rng)
        assert result.hit is True
        assert len(result.damage) == 1
        dr = result.damage[0]
        assert dr.dice_result is not None
        assert len(dr.dice_result.dice) == 1
        assert dr.dice_result.dice[0].sides == 8

    def test_miss_has_no_damage(self) -> None:
        """On miss, damage tuple is empty — no dice_result to check."""
        rng = _rng_returning(1)  # nat 1 = auto miss
        result = resolve_attack(modifier=10, ac=5, attack=_sword(), rng=rng)
        assert result.hit is False
        assert result.damage == ()

    def test_extra_damage_carries_dice_result(self) -> None:
        """Extra damage (e.g. Sneak Attack 2d6) has dice_result with correct die faces."""
        rng = _rng_returning(15, 6, 3, 4)  # d20=15 (hit, no crit), weapon d8=6, sneak 2d6: 3, 4
        result = resolve_attack(
            modifier=5,
            ac=10,
            attack=_sword(),
            extra_damage=(ExtraDamage(dice="2d6", type=DamageType.PIERCING, source="sneak_attack"),),
            rng=rng,
        )
        assert result.hit is True
        sneak = result.damage[1]
        assert sneak.source == "sneak_attack"
        assert sneak.dice_result is not None
        assert len(sneak.dice_result.dice) == 2
        assert all(d.sides == 6 for d in sneak.dice_result.dice)

    def test_critical_produces_separate_crit_damage(self) -> None:
        """On crit, 1d8 → two DamageResults: base (1d8) + crit (1d8)."""
        # nat 20 = crit, base die=4, crit die=5
        rng = _rng_returning(20, 4, 5)
        result = resolve_attack(modifier=0, ac=10, attack=_sword(), rng=rng)
        assert result.critical is True
        assert len(result.damage) == 2
        base = result.damage[0]
        crit = result.damage[1]
        assert base.source == "weapon"
        assert crit.source == "weapon_crit"
        assert base.dice_result is not None
        assert crit.dice_result is not None
        assert len(base.dice_result.dice) == 1
        assert len(crit.dice_result.dice) == 1
        assert all(d.sides == 8 for d in base.dice_result.dice)
        assert all(d.sides == 8 for d in crit.dice_result.dice)

    def test_force_crit_produces_separate_crit_damage(self) -> None:
        """force_crit=True creates separate crit damage even without nat 20."""
        rng = _rng_returning(15, 4, 5)  # d20=15 (hit but not nat20), base die=4, crit die=5
        result = resolve_attack(modifier=5, ac=10, attack=_sword(), force_crit=True, rng=rng)
        assert result.critical is True
        assert len(result.damage) == 2
        assert result.damage[0].source == "weapon"
        assert result.damage[1].source == "weapon_crit"
        assert result.damage[0].dice_result is not None
        assert len(result.damage[0].dice_result.dice) == 1


# ---------------------------------------------------------------------------
# Event data serialization (combat_manager)
# ---------------------------------------------------------------------------


def _atk_mods(**kwargs: object) -> object:
    """Build AttackModifiers with sensible defaults."""
    from dnd_simulator.core.modifiers import AttackModifiers

    defaults: dict[str, object] = {
        "modifier": 5,
        "damage_bonus": 0,
        "dice_bonuses": (),
        "advantage": False,
        "disadvantage": False,
        "force_crit": False,
        "target_ac": 13,
        "roll_components": (),
        "damage_components": (),
    }
    defaults.update(kwargs)
    return AttackModifiers(**defaults)  # type: ignore[arg-type]


class TestBuildAttackEvent:
    """Test _build_attack_event() and _build_damage_components() output."""

    def _make_check_result(
        self,
        *,
        success: bool = True,
        roll: int = 14,
        total: int = 19,
        dc: int = 13,
        critical: bool = False,
        advantage: bool = False,
        alt_roll: int | None = None,
    ) -> CheckResult:
        die = DieRoll(sides=20, result=roll)
        alt = DieRoll(sides=20, result=alt_roll) if alt_roll is not None else None
        d20 = D20Result(die=die, alt=alt, advantage=advantage, disadvantage=not advantage if alt else False)
        return CheckResult(success=success, roll=roll, total=total, dc=dc, critical=critical, d20=d20)

    def test_attack_event_includes_d20(self) -> None:
        from dnd_simulator.rules.combat import AttackResult, DamageResult

        check = self._make_check_result()
        attack_result = AttackResult(
            hit=True,
            critical=False,
            attack_check=check,
            damage=(DamageResult(amount=6, type=DamageType.SLASHING, source="weapon", dice="1d8"),),
            total_damage=6,
        )
        data = build_attack_event("a", "t", _sword(), attack_result, _atk_mods(), [])
        atk_roll = data["attack_roll"]
        assert isinstance(atk_roll, dict)
        assert "d20" in atk_roll
        d20_data = atk_roll["d20"]
        assert isinstance(d20_data, dict)
        assert d20_data["result"] == 14
        assert d20_data["sides"] == 20

    def test_attack_event_advantage_includes_d20_alt(self) -> None:
        from dnd_simulator.rules.combat import AttackResult, DamageResult

        check = self._make_check_result(advantage=True, alt_roll=7)
        attack_result = AttackResult(
            hit=True,
            critical=False,
            attack_check=check,
            damage=(DamageResult(amount=6, type=DamageType.SLASHING, source="weapon", dice="1d8"),),
            total_damage=6,
        )
        data = build_attack_event("a", "t", _sword(), attack_result, _atk_mods(advantage=True), [])
        atk_roll = data["attack_roll"]
        assert isinstance(atk_roll, dict)
        assert "d20_alt" in atk_roll
        d20_alt = atk_roll["d20_alt"]
        assert isinstance(d20_alt, dict)
        assert d20_alt["result"] == 7
        assert d20_alt["sides"] == 20

    def test_damage_components_include_dice_detail(self) -> None:
        from dnd_simulator.rules.combat import AttackResult, DamageResult

        dice_result = DiceResult(
            expression="1d8",
            dice=(DieRoll(sides=8, result=6),),
            flat=0,
            total=6,
        )
        check = self._make_check_result()
        attack_result = AttackResult(
            hit=True,
            critical=False,
            attack_check=check,
            damage=(
                DamageResult(amount=6, type=DamageType.SLASHING, source="weapon", dice="1d8", dice_result=dice_result),
            ),
            total_damage=6,
        )

        components = build_damage_components(attack_result, _atk_mods().damage_components)
        assert len(components) >= 1
        comp = components[0]
        assert "dice_detail" in comp
        dice_detail = comp["dice_detail"]
        assert isinstance(dice_detail, list)
        assert len(dice_detail) == 1
        assert dice_detail[0]["sides"] == 8
        assert dice_detail[0]["result"] == 6

    def test_dice_detail_has_original_on_reroll(self) -> None:
        from dnd_simulator.rules.combat import AttackResult, DamageResult

        dice_result = DiceResult(
            expression="1d8",
            dice=(DieRoll(sides=8, result=5, original=1),),
            flat=0,
            total=5,
        )
        check = self._make_check_result()
        attack_result = AttackResult(
            hit=True,
            critical=False,
            attack_check=check,
            damage=(
                DamageResult(amount=5, type=DamageType.SLASHING, source="weapon", dice="1d8", dice_result=dice_result),
            ),
            total_damage=5,
        )

        components = build_damage_components(attack_result, _atk_mods().damage_components)
        detail = components[0]["dice_detail"]
        assert isinstance(detail, list)
        assert detail[0]["original"] == 1

    def test_flat_damage_has_empty_dice_detail(self) -> None:
        from dnd_simulator.core.modifiers import RollComponent
        from dnd_simulator.rules.combat import AttackResult, DamageResult

        check = self._make_check_result()
        attack_result = AttackResult(
            hit=True,
            critical=False,
            attack_check=check,
            damage=(DamageResult(amount=6, type=DamageType.SLASHING, source="weapon", dice="1d8"),),
            total_damage=8,
        )

        components = build_damage_components(
            attack_result,
            (RollComponent(source="dueling", value=2, dice=""),),
        )
        # The flat "dueling" component should have empty dice_detail
        dueling = [c for c in components if c["source"] == "dueling"]
        assert len(dueling) == 1
        assert dueling[0]["dice_detail"] == []


# ---------------------------------------------------------------------------
# Healing event data
# ---------------------------------------------------------------------------


class TestHealingDiceDetail:
    def test_second_wind_event_has_dice_detail(self) -> None:
        """Second Wind event data includes dice_detail for the 1d10 roll."""
        from unittest.mock import MagicMock

        from dnd_simulator.core.action import Action, ActionType
        from dnd_simulator.core.class_features import FighterFeatures, FightingStyle
        from dnd_simulator.core.models import ActionResult, Event
        from dnd_simulator.core.resource import ResourcePool, RestType
        from dnd_simulator.rules.handlers.items import handle_second_wind

        actor = Character(
            id="fighter",
            name="Fighter",
            location_id="r1",
            max_hp=20,
            current_hp=10,
            level=3,
            class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
            resource_pools=[ResourcePool(id="second_wind", max_uses=1, current_uses=1, reset_on=RestType.SHORT_REST)],
        )

        emitted: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emitted.append(event)
            return ActionResult()

        action = Action(name=ActionType.SECOND_WIND, params={})
        ctx = MagicMock()
        ctx.rng = None
        world = MagicMock()

        handle_second_wind(actor, action, capture_emit, ctx, world)

        assert len(emitted) == 1
        data = emitted[0].data
        assert "dice_detail" in data
        dice_detail = data["dice_detail"]
        assert isinstance(dice_detail, list)
        assert len(dice_detail) == 1
        assert dice_detail[0]["sides"] == 10

    def test_use_potion_event_has_dice_detail(self) -> None:
        """Potion use event data includes dice_detail for heal dice."""
        from unittest.mock import MagicMock

        from dnd_simulator.core.action import Action, ActionType
        from dnd_simulator.core.items import Item, ItemType
        from dnd_simulator.core.models import ActionResult, Event
        from dnd_simulator.rules.handlers.items import handle_use_item

        actor = Character(
            id="hero",
            name="Hero",
            location_id="r1",
            max_hp=20,
            current_hp=10,
            inventory=[
                Item(id="pot1", name="Health Potion", item_type=ItemType.POTION, params={"heal_dice": "2d4+2"}),
            ],
        )

        emitted: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emitted.append(event)
            return ActionResult()

        action = Action(name=ActionType.USE_ITEM, params={"item_id": "pot1"})
        ctx = MagicMock()
        ctx.rng = None
        world = MagicMock()

        handle_use_item(actor, action, capture_emit, ctx, world)

        assert len(emitted) == 1
        data = emitted[0].data
        assert "dice_detail" in data
        dice_detail = data["dice_detail"]
        assert isinstance(dice_detail, list)
        assert len(dice_detail) == 2  # 2d4
        assert all(d["sides"] == 4 for d in dice_detail)


# ---------------------------------------------------------------------------
# Perception formatting unchanged
# ---------------------------------------------------------------------------


class TestPerceptionUnchanged:
    """Verify that perception text formatting still works with enriched event data."""

    def test_format_roll_with_d20_field(self) -> None:
        """_format_roll produces correct text even when d20/d20_alt present."""
        from dnd_simulator.layers.entities.perception import _format_roll

        atk_roll: dict[str, object] = {
            "natural": 14,
            "d20": {"result": 14, "sides": 20},
            "components": [{"source": "ability", "value": 5, "dice": ""}],
            "total": 19,
            "advantage": False,
            "disadvantage": False,
        }
        result = _format_roll(atk_roll, 13)
        assert "d20(14)" in result
        assert "+5" in result
        assert "=19" in result
        assert "AC" in result
        assert "13" in result

    def test_format_roll_with_advantage_and_d20_alt(self) -> None:
        from dnd_simulator.layers.entities.perception import _format_roll

        atk_roll: dict[str, object] = {
            "natural": 14,
            "d20": {"result": 14, "sides": 20},
            "d20_alt": {"result": 7, "sides": 20},
            "components": [{"source": "ability", "value": 3, "dice": ""}],
            "total": 17,
            "advantage": True,
            "disadvantage": False,
        }
        result = _format_roll(atk_roll, 13)
        assert "adv" in result.lower()
        assert "d20(14)" in result

    def test_format_damage_with_dice_detail(self) -> None:
        """_format_damage produces correct text even when dice_detail present."""
        from dnd_simulator.layers.entities.perception import _format_damage

        components: list[dict[str, object]] = [
            {
                "source": "weapon",
                "dice": "1d8",
                "dice_detail": [{"sides": 8, "result": 6}],
                "amount": 6,
                "type": "slashing",
            },
            {
                "source": "sneak_attack",
                "dice": "2d6",
                "dice_detail": [{"sides": 6, "result": 5}, {"sides": 6, "result": 4}],
                "amount": 9,
                "type": "piercing",
            },
            {
                "source": "dueling",
                "dice": "",
                "dice_detail": [],
                "amount": 2,
                "type": "slashing",
            },
        ]
        result = _format_damage(17, components, critical=False)
        assert "17 damage" in result
        assert "1d8" in result
        assert "sneak_attack" in result
