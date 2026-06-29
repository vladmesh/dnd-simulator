"""Reputation-change event carries the faction display name, not the raw slug.

Sprint 020, Phase 4, Task 2 — combat-log i18n: faction-id leak fix.
The E2E phase-3 finding: «Твоя репутация с **kingdom** изменилась» leaked the raw
faction_id slug into the localized log. The event must now resolve and carry the
faction display name (via QueryType.FACTION_NAME), falling back to the slug only
when no name can be resolved.
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
from dnd_simulator.core.models import Answer, EventType, FactionRelation, Query, QueryType
from dnd_simulator.i18n import set_language
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.layers.entities.perception import perceive_event
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


def _hero() -> Character:
    return Character(
        id="hero",
        name="Hero",
        location_id="arena",
        faction_id="heroes",
        max_hp=20,
        current_hp=20,
        ability_scores=AbilityScores(),
        attacks=_ATTACK,
    )


def _victim() -> Creature:
    return Creature(
        id="bandit",
        name="Bandit",
        location_id="arena",
        faction_id="kingdom",
        max_hp=5,
        current_hp=0,  # already dead for _handle_death
        attacks=_ATTACK,
    )


def _make_cm(*creatures: Creature) -> tuple[CombatManager, dict[str, list]]:
    entities: dict[str, Creature] = {c.id: c for c in creatures}
    log: dict[str, list] = {}
    for c in creatures:
        log.setdefault(c.location_id, [])
    return CombatManager(entities, log), log


def _query_fn_with_name(name: str | None):
    """A politics query stub resolving FACTION_NAME to `name`, FACTION_RELATION to NEUTRAL."""

    def qf(layer: str, query: Query) -> Answer:
        if query.question is QueryType.FACTION_NAME:
            return Answer(value=name)
        if query.question is QueryType.FACTION_RELATION:
            return Answer(value=FactionRelation.NEUTRAL)
        return Answer(value=None)

    return qf


def _entity_lookup(*entities: Creature):
    by_id = {e.id: e for e in entities}
    return lambda eid: by_id.get(eid)


class TestReputationEventFactionName:
    def teardown_method(self) -> None:
        set_language("en")

    def test_event_carries_display_name_not_slug(self) -> None:
        """A kill that drops reputation tags the event with the faction's display name."""
        hero, victim = _hero(), _victim()
        cm, log = _make_cm(hero, victim)

        cm._handle_death(hero, victim, victim.id, _hit_result(), query_fn=_query_fn_with_name("Royal Court"))

        rep_ev = next(e for e in log["arena"] if e.event_type == EventType.REPUTATION_CHANGED)
        assert rep_ev.data["faction_name"] == "Royal Court"
        assert rep_ev.data["faction_id"] == "kingdom"

        line = perceive_event(rep_ev, hero, _entity_lookup(hero, victim))
        assert "Royal Court" in line
        assert "kingdom" not in line  # raw slug must not leak

    def test_no_query_fn_omits_faction_name_and_still_renders(self) -> None:
        """Without a query_fn the event omits faction_name; perception falls back to the slug, no crash."""
        hero, victim = _hero(), _victim()
        cm, log = _make_cm(hero, victim)

        cm._handle_death(hero, victim, victim.id, _hit_result())  # no query_fn

        rep_ev = next(e for e in log["arena"] if e.event_type == EventType.REPUTATION_CHANGED)
        assert "faction_name" not in rep_ev.data

        line = perceive_event(rep_ev, hero, _entity_lookup(hero, victim))
        assert "kingdom" in line  # graceful fallback to the id

    def test_unresolvable_faction_name_omitted(self) -> None:
        """A query_fn that returns no name leaves faction_name off so the slug fallback applies."""
        hero, victim = _hero(), _victim()
        cm, log = _make_cm(hero, victim)

        cm._handle_death(hero, victim, victim.id, _hit_result(), query_fn=_query_fn_with_name(None))

        rep_ev = next(e for e in log["arena"] if e.event_type == EventType.REPUTATION_CHANGED)
        assert "faction_name" not in rep_ev.data
