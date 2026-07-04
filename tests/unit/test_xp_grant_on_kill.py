"""Unit tests for XP grant on kill in combat_resolution.handle_death.

Sprint 017, Phase 1, Task 2.
"""

from __future__ import annotations

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    Creature,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.layers.entities import combat_resolution
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.rules.checks import CheckResult
from dnd_simulator.rules.combat import AttackResult

_ATTACK = (
    Attack(
        name="melee",
        ability=Ability.STR,
        damage=(DamageComponent(dice="1d6", type=DamageType.SLASHING),),
        reach=5,
    ),
)


def _hit_result() -> AttackResult:
    return AttackResult(
        hit=True,
        critical=False,
        attack_check=CheckResult(success=True, roll=15, total=20, dc=10, critical=False),
        damage=(),
        total_damage=10,
    )


def _character(cid: str = "hero", *, level: int = 1, experience: int = 0) -> Character:
    c = Character(
        id=cid,
        name=cid.capitalize(),
        location_id="arena",
        faction_id="heroes",
        max_hp=20,
        current_hp=20,
        ability_scores=AbilityScores(),
        attacks=_ATTACK,
        level=level,
        experience=experience,
    )
    return c


def _monster(cid: str = "goblin", *, xp_value: int = 50) -> Creature:
    return Creature(
        id=cid,
        name=cid.capitalize(),
        location_id="arena",
        faction_id="goblins",
        max_hp=5,
        current_hp=0,  # already dead for _handle_death
        attacks=_ATTACK,
        xp_value=xp_value,
    )


def _make_cm(*creatures: Creature) -> tuple[CombatManager, dict[str, list[Event]]]:
    entities: dict[str, Creature] = {c.id: c for c in creatures}
    log: dict[str, list[Event]] = {}
    for c in creatures:
        log.setdefault(c.location_id, [])
    return CombatManager(entities, log), log


class TestXpGrantOnKill:
    def test_character_kills_monster_gains_xp(self) -> None:
        hero = _character(experience=0)
        goblin = _monster(xp_value=50)
        cm, log = _make_cm(hero, goblin)

        combat_resolution.handle_death(cm, hero, goblin, goblin.id, _hit_result())

        assert hero.experience == 50
        assert hero.level_up_available is False
        xp_events = [e for e in log["arena"] if e.event_type == EventType.XP_GAINED]
        assert len(xp_events) == 1
        ev = xp_events[0]
        assert ev.data["entity_id"] == hero.id
        assert ev.data["amount"] == 50
        assert ev.data["new_total"] == 50
        assert ev.data["source_entity_id"] == goblin.id
        assert ev.data["level_up_available"] is False

    def test_kill_enough_to_level_up_sets_flag(self) -> None:
        hero = _character(experience=280, level=1)
        goblin = _monster(xp_value=50)
        cm, log = _make_cm(hero, goblin)

        combat_resolution.handle_death(cm, hero, goblin, goblin.id, _hit_result())

        assert hero.experience == 330
        assert hero.level_up_available is True
        assert hero.level == 1  # level itself does not auto-change
        xp_ev = next(e for e in log["arena"] if e.event_type == EventType.XP_GAINED)
        assert xp_ev.data["level_up_available"] is True

    def test_character_kills_character_no_xp(self) -> None:
        hero = _character("hero", experience=0)
        rival = _character("rival")
        rival.current_hp = 0
        cm, log = _make_cm(hero, rival)

        combat_resolution.handle_death(cm, hero, rival, rival.id, _hit_result())

        assert hero.experience == 0
        assert not any(e.event_type == EventType.XP_GAINED for e in log["arena"])

    def test_non_character_attacker_gets_no_xp(self) -> None:
        beast = Creature(
            id="beast",
            name="Beast",
            location_id="arena",
            faction_id="wild",
            max_hp=20,
            current_hp=20,
            attacks=_ATTACK,
        )
        victim = _character("victim")
        victim.current_hp = 0
        victim.xp_value = 100  # even if target had xp_value, beast is not Character
        cm, log = _make_cm(beast, victim)

        combat_resolution.handle_death(cm, beast, victim, victim.id, _hit_result())

        assert not hasattr(beast, "experience")
        assert not any(e.event_type == EventType.XP_GAINED for e in log["arena"])


class TestMonsterTemplateSpawnXp:
    def test_spawn_sets_xp_value_from_cr(self) -> None:
        template = MonsterTemplate(
            id="orc",
            name="Orc",
            hp=15,
            ac=13,
            speed=30,
            ability_scores=AbilityScores(),
            attacks=_ATTACK,
            cr=2.0,
        )
        spawned = template.spawn(location_id="arena", instance_id="orc_1")
        assert spawned.xp_value == 450  # CR 2 → 450 XP per DMG

    def test_spawn_fractional_cr(self) -> None:
        template = MonsterTemplate(
            id="rat",
            name="Rat",
            hp=1,
            ac=10,
            speed=20,
            ability_scores=AbilityScores(),
            attacks=_ATTACK,
            cr=0.125,
        )
        spawned = template.spawn(location_id="arena", instance_id="rat_1")
        assert spawned.xp_value == 25
