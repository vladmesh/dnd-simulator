"""Branch coverage for layers/entities/combat_resolution.py: missing actors, no-combat moves, kill reputation."""

from __future__ import annotations

from collections import defaultdict

from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.container import Container
from dnd_simulator.core.events import AttackRequestedPayload, EntityMovePayload
from dnd_simulator.core.models import Answer, Event, EventType, FactionRelation, Query, QueryType
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.layers.entities.combat_resolution import (
    handle_death,
    is_faction_friendly,
    resolve_attack,
    resolve_move,
)
from dnd_simulator.rules.checks import CheckResult
from dnd_simulator.rules.combat import AttackResult


def _creature(creature_id: str, faction_id: str = "", hp: int = 10) -> Creature:
    return Creature(
        id=creature_id,
        name=creature_id,
        location_id="arena",
        max_hp=10,
        current_hp=hp,
        ac=10,
        speed=30,
        faction_id=faction_id,
    )


def _manager(*entities: Creature | Container) -> CombatManager:
    return CombatManager({entity.id: entity for entity in entities}, defaultdict(list))


def _move_event(entity_id: str) -> Event:
    return Event(
        event_type=EventType.ENTITY_MOVE,
        source_layer="entities",
        data=EntityMovePayload(entity_id, "arena", direction="north", ft=5),
    )


def _attack_event(attacker_id: str, target_id: str) -> Event:
    return Event(
        event_type=EventType.ENTITY_ATTACK_REQUESTED,
        source_layer="entities",
        data=AttackRequestedPayload(attacker_id, target_id),
    )


def _relation_query(relation: FactionRelation):  # type: ignore[no-untyped-def]
    def query_fn(layer: str, query: Query) -> Answer:
        assert query.question is QueryType.FACTION_RELATION
        return Answer(value=relation)

    return query_fn


class TestResolveMove:
    def test_unknown_mover_fails(self) -> None:
        result = resolve_move(_manager(), _move_event("ghost"))
        assert result.success is False
        assert result.error

    def test_mover_without_combat_fails(self) -> None:
        result = resolve_move(_manager(_creature("hero")), _move_event("hero"))
        assert result.success is False
        assert result.error

    def test_mover_in_combat_steps(self) -> None:
        hero = _creature("hero")
        mgr = _manager(hero)
        bm = BattleMap(width=10, height=10)
        bm.set_position("hero", Position(5, 5))
        mgr._combats["arena"] = CombatState(
            location_id="arena", turn_order=["hero"], round_number=1, rounds_without_attack=0, battle_map=bm
        )

        result = resolve_move(mgr, _move_event("hero"))

        assert result.success is True
        assert bm.get_position("hero") != Position(5, 5)


class TestIsFactionFriendly:
    def test_no_query_fn_is_not_friendly(self) -> None:
        hero = _creature("hero", "guild")
        assert is_faction_friendly(_manager(hero, _creature("ally", "guild")), hero, "ally", None) is False

    def test_non_creature_candidate_is_not_friendly(self) -> None:
        hero = _creature("hero", "guild")
        mgr = _manager(hero, Container(id="chest", name="Chest", location_id="arena"))
        assert is_faction_friendly(mgr, hero, "chest", _relation_query(FactionRelation.FRIENDLY)) is False

    def test_friendly_relation_is_friendly(self) -> None:
        hero = _creature("hero", "guild")
        mgr = _manager(hero, _creature("ally", "town"))
        assert is_faction_friendly(mgr, hero, "ally", _relation_query(FactionRelation.FRIENDLY)) is True


class TestResolveAttackMissingTarget:
    def test_unknown_target_fails(self) -> None:
        result = resolve_attack(_manager(_creature("hero")), _attack_event("hero", "ghost"))
        assert result.success is False
        assert result.error


class TestHandleDeathReputation:
    def test_kill_without_query_fn_starts_from_full_reputation(self) -> None:
        killer = _creature("hero", "guild")
        victim = _creature("guard", "town", hp=0)
        mgr = _manager(killer, victim)
        hit = AttackResult(
            hit=True,
            critical=False,
            attack_check=CheckResult(success=True, roll=15, total=15, dc=10, critical=False),
            damage=(),
            total_damage=10,
        )

        handle_death(mgr, killer, victim, "guard", hit, None)

        assert killer.reputation["town"] < 100
        rep_events = [event for event in mgr._location_log["arena"] if event.event_type is EventType.REPUTATION_CHANGED]
        assert rep_events
        assert all(event.data.old_rep == 100 for event in rep_events)  # type: ignore[union-attr]
