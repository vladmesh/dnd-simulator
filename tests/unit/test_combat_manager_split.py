"""Tests for combat manager split (sprint 014, phase 0, task 2).

Tests extracted functions: check_sneak_attack (pure), find_adjacent_ally,
attack event builders, and combat stalemate with named constants.
"""

from __future__ import annotations

import random
from collections import defaultdict

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
from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.core.models import Event
from dnd_simulator.layers.entities.combat_manager import (
    IDLE_ROUNDS_TO_END_COMBAT,
    INITIAL_REACTION_BUDGET,
    CombatManager,
)
from dnd_simulator.rules.combat import AttackResult, resolve_attack
from dnd_simulator.rules.handlers.attack_resolution import build_attack_event, build_damage_components
from dnd_simulator.rules.sneak_attack import check_sneak_attack, find_adjacent_ally

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rapier_attack() -> Attack:
    return Attack(
        name="rapier strike",
        ability=Ability.DEX,
        damage=(DamageComponent("1d8", DamageType.PIERCING),),
        reach=5,
        is_finesse=True,
    )


def _longbow_attack() -> Attack:
    return Attack(
        name="longbow shot",
        ability=Ability.DEX,
        damage=(DamageComponent("1d8", DamageType.PIERCING),),
        reach=150,
    )


def _rogue(level: int = 1, sa_dice: int = 1) -> Character:
    scores = AbilityScores()
    scores[Ability.DEX] = 18
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
        faction_id="party",
        attacks=(_rapier_attack(),),
        class_features=[RogueFeatures(sneak_attack_dice=sa_dice)],
    )


def _fighter() -> Character:
    scores = AbilityScores()
    scores[Ability.STR] = 16
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
        faction_id="party",
    )


def _goblin(entity_id: str = "goblin") -> Creature:
    return Creature(
        id=entity_id,
        name="Goblin",
        location_id="loc",
        ac=12,
        current_hp=10,
        max_hp=10,
        speed=30,
        faction_id="goblins",
    )


def _sword() -> Attack:
    return Attack(
        name="longsword",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )


# ---------------------------------------------------------------------------
# check_sneak_attack (pure function)
# ---------------------------------------------------------------------------


class TestCheckSneakAttack:
    """Pure check_sneak_attack: combines dice check, eligibility, ExtraDamage."""

    def test_eligible_with_ally_adjacent(self) -> None:
        rogue = _rogue(sa_dice=2)
        result = check_sneak_attack(
            rogue,
            _rapier_attack(),
            advantage=False,
            disadvantage=False,
            already_used=False,
            ally_adjacent=True,
        )
        assert len(result) == 1
        assert result[0].source == "sneak_attack"
        assert result[0].dice == "2d6"

    def test_not_eligible_without_ally_or_advantage(self) -> None:
        rogue = _rogue(sa_dice=1)
        result = check_sneak_attack(
            rogue,
            _rapier_attack(),
            advantage=False,
            disadvantage=False,
            already_used=False,
            ally_adjacent=False,
        )
        assert result == ()

    def test_ranged_weapon_with_ally_adjacent(self) -> None:
        rogue = _rogue(sa_dice=1)
        result = check_sneak_attack(
            rogue,
            _longbow_attack(),
            advantage=False,
            disadvantage=False,
            already_used=False,
            ally_adjacent=True,
        )
        assert len(result) == 1
        assert result[0].source == "sneak_attack"

    def test_already_used_returns_empty(self) -> None:
        rogue = _rogue(sa_dice=1)
        result = check_sneak_attack(
            rogue,
            _rapier_attack(),
            advantage=True,
            disadvantage=False,
            already_used=True,
            ally_adjacent=False,
        )
        assert result == ()

    def test_non_rogue_returns_empty(self) -> None:
        fighter = _fighter()
        result = check_sneak_attack(
            fighter,
            _rapier_attack(),
            advantage=True,
            disadvantage=False,
            already_used=False,
            ally_adjacent=False,
        )
        assert result == ()


# ---------------------------------------------------------------------------
# find_adjacent_ally (pure function)
# ---------------------------------------------------------------------------


class TestFindAdjacentAlly:
    """find_adjacent_ally: checks battle map for allies within 5ft of target."""

    def test_ally_within_5ft_returns_true(self) -> None:
        entities: dict[str, Creature] = {
            "rogue": _rogue(),
            "target": _goblin("target"),
            "fighter": _fighter(),
        }
        bm = BattleMap(width=60, height=60)
        bm.set_position("rogue", Position(30, 30))
        bm.set_position("target", Position(35, 30))
        bm.set_position("fighter", Position(35, 35))  # 5ft from target

        result = find_adjacent_ally(
            attacker_id="rogue",
            target_id="target",
            battle_map=bm,
            entities=entities,
            is_ally=lambda eid: entities[eid].faction_id == "party",
        )
        assert result is True

    def test_no_ally_returns_false(self) -> None:
        entities: dict[str, Creature] = {
            "rogue": _rogue(),
            "target": _goblin("target"),
        }
        bm = BattleMap(width=60, height=60)
        bm.set_position("rogue", Position(30, 30))
        bm.set_position("target", Position(35, 30))

        result = find_adjacent_ally(
            attacker_id="rogue",
            target_id="target",
            battle_map=bm,
            entities=entities,
            is_ally=lambda eid: entities[eid].faction_id == "party",
        )
        assert result is False

    def test_enemy_adjacent_not_counted(self) -> None:
        """Enemy within 5ft of target doesn't count as ally."""
        entities: dict[str, Creature] = {
            "rogue": _rogue(),
            "target": _goblin("target"),
            "goblin2": _goblin("goblin2"),
        }
        bm = BattleMap(width=60, height=60)
        bm.set_position("rogue", Position(30, 30))
        bm.set_position("target", Position(35, 30))
        bm.set_position("goblin2", Position(35, 35))

        result = find_adjacent_ally(
            attacker_id="rogue",
            target_id="target",
            battle_map=bm,
            entities=entities,
            is_ally=lambda eid: entities[eid].faction_id == "party",
        )
        assert result is False

    def test_dead_ally_not_counted(self) -> None:
        """Dead ally within 5ft doesn't count."""
        fighter = _fighter()
        fighter.current_hp = 0
        entities: dict[str, Creature] = {
            "rogue": _rogue(),
            "target": _goblin("target"),
            "fighter": fighter,
        }
        bm = BattleMap(width=60, height=60)
        bm.set_position("rogue", Position(30, 30))
        bm.set_position("target", Position(35, 30))
        bm.set_position("fighter", Position(35, 35))

        result = find_adjacent_ally(
            attacker_id="rogue",
            target_id="target",
            battle_map=bm,
            entities=entities,
            is_ally=lambda eid: entities[eid].faction_id == "party",
        )
        assert result is False


# ---------------------------------------------------------------------------
# Attack resolution boundary tests
# ---------------------------------------------------------------------------


class TestAttackResolutionBoundary:
    """Exact boundary: roll + modifier == AC is a hit; roll + modifier < AC is a miss."""

    def test_roll_10_mod_5_vs_ac_15_hits(self) -> None:
        """10 + 5 = 15 >= 15 → hit."""
        rng = random.Random()
        rng.randint = lambda a, b: 10  # type: ignore[method-assign]
        result = resolve_attack(modifier=5, ac=15, attack=_sword(), rng=rng)
        assert result.hit is True

    def test_roll_9_mod_5_vs_ac_15_misses(self) -> None:
        """9 + 5 = 14 < 15 → miss."""
        rng = random.Random()
        rng.randint = lambda a, b: 9  # type: ignore[method-assign]
        result = resolve_attack(modifier=5, ac=15, attack=_sword(), rng=rng)
        assert result.hit is False

    def test_natural_20_doubles_damage_dice(self) -> None:
        """Critical hit produces base + crit damage components."""
        rng = random.Random()
        rng.randint = lambda a, b: 20  # type: ignore[method-assign]
        result = resolve_attack(modifier=0, ac=25, attack=_sword(), rng=rng)
        assert result.hit is True
        assert result.critical is True
        sources = [d.source for d in result.damage]
        assert "weapon" in sources
        assert "weapon_crit" in sources


# ---------------------------------------------------------------------------
# Combat stalemate with named constant
# ---------------------------------------------------------------------------


class TestCombatStalemate:
    """2 consecutive idle rounds → combat ends (via named constant)."""

    def test_stalemate_constant_is_2(self) -> None:
        assert IDLE_ROUNDS_TO_END_COMBAT == 2

    def test_initial_reaction_budget_is_1(self) -> None:
        assert INITIAL_REACTION_BUDGET == 1

    def test_stalemate_ends_combat(self) -> None:
        c1 = Creature(id="c1", name="C1", location_id="arena", ac=10, current_hp=10, max_hp=10, faction_id="a")
        c2 = Creature(id="c2", name="C2", location_id="arena", ac=10, current_hp=10, max_hp=10, faction_id="b")
        entities: dict[str, Creature] = {"c1": c1, "c2": c2}
        log: dict[str, list[Event]] = defaultdict(list)
        cm = CombatManager(entities, log)  # type: ignore[arg-type]
        cm.start_combat("arena")
        assert cm.get_combat("arena") is not None
        # Round 1: no attacks
        cm.end_combat_round("arena")
        assert cm.get_combat("arena") is not None
        # Round 2: no attacks → stalemate
        cm.end_combat_round("arena")
        assert cm.get_combat("arena") is None


# ---------------------------------------------------------------------------
# Event builder tests
# ---------------------------------------------------------------------------


class TestBuildAttackEvent:
    """build_attack_event produces correct event data structure."""

    def test_builds_event_with_hit(self) -> None:
        from dnd_simulator.core.modifiers import AttackModifiers
        from dnd_simulator.core.rolls import D20Result, DieRoll
        from dnd_simulator.rules.checks import CheckResult

        check = CheckResult(
            success=True,
            roll=15,
            total=20,
            dc=15,
            critical=False,
            d20=D20Result(die=DieRoll(sides=20, result=15)),
        )
        atk_result = AttackResult(
            hit=True,
            critical=False,
            attack_check=check,
            damage=(),
            total_damage=0,
        )
        mods = AttackModifiers(
            modifier=5,
            damage_bonus=0,
            dice_bonuses=(),
            advantage=False,
            disadvantage=False,
            force_crit=False,
            target_ac=15,
        )
        data = build_attack_event("att", "tgt", _sword(), atk_result, mods, [])
        assert data["attacker_id"] == "att"
        assert data["target_id"] == "tgt"
        assert data["hit"] is True
        assert data["critical"] is False
        assert data["weapon"] == "longsword"
        assert data["ac"] == 15


class TestBuildDamageComponents:
    """build_damage_components produces correct component list."""

    def test_builds_weapon_damage(self) -> None:
        from dnd_simulator.core.modifiers import RollComponent
        from dnd_simulator.core.rolls import DiceResult, DieRoll
        from dnd_simulator.rules.combat import DamageResult

        dr = DamageResult(
            amount=5,
            type=DamageType.SLASHING,
            source="weapon",
            dice="1d8",
            dice_result=DiceResult(expression="1d8", dice=(DieRoll(sides=8, result=5),), flat=0, total=5),
        )
        atk_result = AttackResult(
            hit=True,
            critical=False,
            attack_check=None,  # type: ignore[arg-type]
            damage=(dr,),
            total_damage=8,
        )
        damage_comps = [RollComponent(source="str", value=3)]
        components = build_damage_components(atk_result, damage_comps)
        assert len(components) == 2  # weapon + str bonus
        assert components[0]["source"] == "weapon"
        assert components[0]["amount"] == 5
        assert components[1]["source"] == "str"
        assert components[1]["amount"] == 3
