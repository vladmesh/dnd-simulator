"""Tests for Sneak Attack faction-aware ally detection.

_check_sneak_attack must use faction relations to determine if an adjacent
creature is an ally (FRIENDLY) of the attacker, not just "any alive creature."
"""

from __future__ import annotations

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
from dnd_simulator.core.combat import Position
from dnd_simulator.core.models import Answer, Event, Query, QueryType
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.layers.politics.models import FactionRelation
from dnd_simulator.rules.sneak_attack import check_sneak_attack, find_adjacent_ally
from dnd_simulator.rules.weapons import get_weapon_attack


def _rapier_attack() -> Attack:
    return Attack(
        name="rapier strike",
        ability=Ability.DEX,
        damage=(DamageComponent("1d8", DamageType.PIERCING),),
        reach=5,
        is_finesse=True,
    )


def _rogue(*, faction_id: str = "party") -> Character:
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
        level=1,
        faction_id=faction_id,
        attacks=(_rapier_attack(),),
        class_features=[RogueFeatures(sneak_attack_dice=1)],
    )


def _goblin(*, entity_id: str = "goblin", faction_id: str = "goblins") -> Creature:
    return Creature(
        id=entity_id,
        name="Goblin",
        location_id="loc",
        ac=12,
        current_hp=10,
        max_hp=10,
        speed=30,
        faction_id=faction_id,
    )


def _fighter(*, faction_id: str = "party") -> Character:
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
        faction_id=faction_id,
    )


def _bystander(*, faction_id: str = "townsfolk") -> Creature:
    return Creature(
        id="bystander",
        name="Bystander",
        location_id="loc",
        ac=10,
        current_hp=5,
        max_hp=5,
        speed=30,
        faction_id=faction_id,
    )


def _make_faction_query(relations: dict[tuple[str, str], FactionRelation]):
    """Build a query_fn that answers FACTION_RELATION queries."""

    def query_fn(layer: str, query: Query) -> Answer:
        if query.question is QueryType.FACTION_RELATION:
            a = str(query.params["a"])
            b = str(query.params["b"])
            if a == b:
                return Answer(value=FactionRelation.FRIENDLY)
            key = (min(a, b), max(a, b))
            relation = relations.get(key, FactionRelation.NEUTRAL)
            return Answer(value=relation)
        return Answer(value=None)

    return query_fn


def _is_ally_via_query(attacker: Creature, candidate: Creature, query_fn: object) -> bool:
    """Check if candidate is FRIENDLY to attacker using query_fn."""
    answer = query_fn(  # type: ignore[operator]
        "politics",
        Query(question=QueryType.FACTION_RELATION, params={"a": attacker.faction_id, "b": candidate.faction_id}),
    )
    return answer.value == FactionRelation.FRIENDLY


def _setup_combat(
    *creatures: Creature,
    positions: dict[str, Position],
) -> CombatManager:
    """Create a CombatManager with pre-placed creatures in combat."""
    entities: dict[str, Creature] = {c.id: c for c in creatures}
    location_log: dict[str, list[Event]] = defaultdict(list)
    cm = CombatManager(entities, location_log)  # type: ignore[arg-type]
    cm.start_combat("loc")
    combat = cm.get_combat("loc")
    assert combat is not None
    for eid, pos in positions.items():
        combat.battle_map.set_position(eid, pos)
    return cm


class TestSneakAttackFactionCheck:
    """SA ally detection must use faction relations, not just proximity."""

    def _check_sa(
        self,
        rogue: Character,
        target_id: str,
        cm: CombatManager,
        query_fn: object,
        *,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> tuple[object, ...]:
        """Helper: compute ally adjacency via find_adjacent_ally, then check_sneak_attack."""
        combat = cm.get_combat("loc")
        assert combat is not None
        entities: dict[str, Creature] = {
            eid: cm._entities[eid] for eid in cm._entities if isinstance(cm._entities[eid], Creature)
        }  # type: ignore[misc]

        ally_adjacent = find_adjacent_ally(
            attacker_id=rogue.id,
            target_id=target_id,
            battle_map=combat.battle_map,
            entities=entities,
            is_ally=lambda eid: _is_ally_via_query(rogue, entities[eid], query_fn),
        )
        attack = get_weapon_attack(rogue)
        return check_sneak_attack(
            rogue,
            attack,
            advantage=advantage,
            disadvantage=disadvantage,
            already_used=False,
            ally_adjacent=ally_adjacent,
        )

    def test_sa_granted_when_friendly_ally_adjacent(self) -> None:
        """Rogue attacks goblin. Fighter (same faction, FRIENDLY) within 5ft of target."""
        rogue = _rogue(faction_id="party")
        target = _goblin(entity_id="target", faction_id="goblins")
        ally = _fighter(faction_id="party")

        cm = _setup_combat(
            rogue,
            target,
            ally,
            positions={
                "rogue": Position(30, 30),
                "target": Position(35, 30),
                "fighter": Position(35, 35),
            },
        )
        query_fn = _make_faction_query(
            {
                (min("goblins", "party"), max("goblins", "party")): FactionRelation.HOSTILE,
            }
        )
        result = self._check_sa(rogue, "target", cm, query_fn)
        assert len(result) == 1
        assert result[0].source == "sneak_attack"

    def test_sa_denied_when_only_enemies_adjacent(self) -> None:
        """Rogue attacks goblin. Another goblin (HOSTILE to rogue) within 5ft — not an ally."""
        rogue = _rogue(faction_id="party")
        target = _goblin(entity_id="target", faction_id="goblins")
        other_goblin = _goblin(entity_id="goblin2", faction_id="goblins")

        cm = _setup_combat(
            rogue,
            target,
            other_goblin,
            positions={
                "rogue": Position(30, 30),
                "target": Position(35, 30),
                "goblin2": Position(35, 35),
            },
        )
        query_fn = _make_faction_query(
            {
                (min("goblins", "party"), max("goblins", "party")): FactionRelation.HOSTILE,
            }
        )
        result = self._check_sa(rogue, "target", cm, query_fn)
        assert result == ()

    def test_sa_denied_when_only_neutral_adjacent(self) -> None:
        """Rogue attacks goblin. A bystander (NEUTRAL) within 5ft — not an ally."""
        rogue = _rogue(faction_id="party")
        target = _goblin(entity_id="target", faction_id="goblins")
        bystander = _bystander(faction_id="townsfolk")

        cm = _setup_combat(
            rogue,
            target,
            bystander,
            positions={
                "rogue": Position(30, 30),
                "target": Position(35, 30),
                "bystander": Position(35, 35),
            },
        )
        query_fn = _make_faction_query({})
        result = self._check_sa(rogue, "target", cm, query_fn)
        assert result == ()

    def test_sa_via_advantage_ignores_faction(self) -> None:
        """Rogue has advantage. No allies adjacent. SA eligible (advantage path unchanged)."""
        rogue = _rogue(faction_id="party")
        target = _goblin(entity_id="target", faction_id="goblins")

        cm = _setup_combat(
            rogue,
            target,
            positions={
                "rogue": Position(30, 30),
                "target": Position(35, 30),
            },
        )
        query_fn = _make_faction_query({})
        result = self._check_sa(rogue, "target", cm, query_fn, advantage=True)
        assert len(result) == 1
        assert result[0].source == "sneak_attack"

    def test_sa_denied_no_creatures_adjacent(self) -> None:
        """Only attacker and target on map. No advantage. SA not eligible."""
        rogue = _rogue(faction_id="party")
        target = _goblin(entity_id="target", faction_id="goblins")

        cm = _setup_combat(
            rogue,
            target,
            positions={
                "rogue": Position(30, 30),
                "target": Position(35, 30),
            },
        )
        query_fn = _make_faction_query({})
        result = self._check_sa(rogue, "target", cm, query_fn)
        assert result == ()
