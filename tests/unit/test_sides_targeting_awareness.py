"""Tests for sides-based targeting and awareness in combat.

Combat hostility uses CombatState.sides as single source of truth.
Out of combat, faction relation queries remain unchanged.
"""

from __future__ import annotations

import random

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.class_features import RogueFeatures
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, FactionRelation, Query, QueryType
from dnd_simulator.layers.entities.layer import EntitiesLayer

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)

_DAGGER_FINESSE = Attack(
    name="dagger",
    ability=Ability.DEX,
    damage=(DamageComponent("1d4", DamageType.PIERCING),),
    is_finesse=True,
)


def _scores(**overrides: int) -> AbilityScores:
    scores = dict(AbilityScores().scores)
    for name, val in overrides.items():
        scores[Ability[name.upper()]] = val
    return AbilityScores(scores=scores)


def _noop_query_fn(target: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _setup_combat(
    layer: EntitiesLayer,
    location: str,
    positions: dict[str, tuple[int, int]],
    sides: dict[int, set[str]],
    entity_to_side: dict[str, int],
) -> CombatState:
    """Helper to set up a combat with positions and sides."""
    battle_map = BattleMap(width=60, height=60)
    for eid, (x, y) in positions.items():
        battle_map.set_position(eid, Position(x, y))
    combat = CombatState(
        location_id=location,
        turn_order=list(positions.keys()),
        battle_map=battle_map,
        sides=sides,
        entity_to_side=entity_to_side,
    )
    layer._combat._combats[location] = combat
    return combat


class TestCombatAwarenessUsesSides:
    """In combat, is_hostile is determined by combat sides, not faction queries."""

    def test_same_side_not_hostile(self) -> None:
        """Goblin sees other goblins as not hostile when on the same combat side."""
        g1 = Character(id="g1", name="Goblin1", location_id="arena", faction_id="goblins", in_combat=True)
        g2 = Character(id="g2", name="Goblin2", location_id="arena", faction_id="goblins", in_combat=True)
        guard = Character(id="h1", name="Guard", location_id="arena", faction_id="guards", in_combat=True)

        layer = EntitiesLayer([g1, g2, guard])
        _setup_combat(
            layer,
            "arena",
            {"g1": (10, 10), "g2": (15, 10), "h1": (30, 10)},
            sides={0: {"g1", "g2"}, 1: {"h1"}},
            entity_to_side={"g1": 0, "g2": 0, "h1": 1},
        )

        awareness = layer.build_combat_awareness(g1)
        nearby_by_id = {n.id: n for n in awareness.nearby}
        assert nearby_by_id["g2"].is_hostile is False
        assert nearby_by_id["h1"].is_hostile is True

    def test_friendly_factions_same_side_not_hostile(self) -> None:
        """Goblins + bandits (FRIENDLY) merged into same side. Bandit sees goblins as allies."""
        goblin = Character(id="g1", name="Goblin", location_id="arena", faction_id="goblins", in_combat=True)
        bandit = Character(id="b1", name="Bandit", location_id="arena", faction_id="bandits", in_combat=True)
        guard = Character(id="h1", name="Guard", location_id="arena", faction_id="guards", in_combat=True)

        layer = EntitiesLayer([goblin, bandit, guard])
        _setup_combat(
            layer,
            "arena",
            {"g1": (10, 10), "b1": (15, 10), "h1": (30, 10)},
            sides={0: {"g1", "b1"}, 1: {"h1"}},
            entity_to_side={"g1": 0, "b1": 0, "h1": 1},
        )

        awareness = layer.build_combat_awareness(bandit)
        nearby_by_id = {n.id: n for n in awareness.nearby}
        assert nearby_by_id["g1"].is_hostile is False
        assert nearby_by_id["h1"].is_hostile is True

    def test_no_politics_queries_when_sides_exist(self) -> None:
        """When combat has sides, is_hostile uses sides — no faction relation queries."""
        g1 = Character(id="g1", name="Goblin", location_id="arena", faction_id="goblins", in_combat=True)
        guard = Character(id="h1", name="Guard", location_id="arena", faction_id="guards", in_combat=True)

        layer = EntitiesLayer([g1, guard])
        _setup_combat(
            layer,
            "arena",
            {"g1": (10, 10), "h1": (30, 10)},
            sides={0: {"g1"}, 1: {"h1"}},
            entity_to_side={"g1": 0, "h1": 1},
        )

        faction_queries: list[Query] = []

        def spy_query_fn(target: str, query: Query) -> Answer:
            if target == "politics" and query.question == QueryType.FACTION_RELATION:
                faction_queries.append(query)
            return Answer(value=FactionRelation.HOSTILE)

        awareness = layer.build_combat_awareness(g1, query_fn=spy_query_fn)
        assert len(faction_queries) == 0
        assert awareness.nearby[0].is_hostile is True

    def test_fallback_to_faction_query_when_no_sides(self) -> None:
        """Combat without sides (started without query_fn) falls back to faction queries."""
        g1 = Character(id="g1", name="Goblin", location_id="arena", faction_id="goblins", in_combat=True)
        guard = Character(id="h1", name="Guard", location_id="arena", faction_id="guards", in_combat=True)

        layer = EntitiesLayer([g1, guard])
        # Combat without sides (empty dicts)
        _setup_combat(
            layer,
            "arena",
            {"g1": (10, 10), "h1": (30, 10)},
            sides={},
            entity_to_side={},
        )

        def query_fn(target: str, query: Query) -> Answer:
            if target == "politics" and query.question == QueryType.FACTION_RELATION:
                return Answer(value=FactionRelation.HOSTILE)
            return Answer(value=None)

        awareness = layer.build_combat_awareness(g1, query_fn=query_fn)
        assert awareness.nearby[0].is_hostile is True


class TestOutOfCombatHostilityUnchanged:
    """Out of combat, hostility uses faction relation queries — no sides exist."""

    def test_hostile_faction_hostile_outside_combat(self) -> None:
        knight = Character(id="k1", name="Knight", location_id="road", faction_id="kingdom")
        orc = Character(id="o1", name="Orc", location_id="road", faction_id="horde")

        layer = EntitiesLayer([knight, orc])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "politics" and query.question == QueryType.FACTION_RELATION:
                return Answer(value=FactionRelation.HOSTILE)
            return Answer(value=None)

        nearby = layer.build_nearby_entities(knight, hour=12, query_fn=query_fn)
        assert len(nearby) == 1
        assert nearby[0].is_hostile is True

    def test_friendly_faction_not_hostile_outside_combat(self) -> None:
        knight = Character(id="k1", name="Knight", location_id="road", faction_id="kingdom")
        ally = Character(id="a1", name="Ally", location_id="road", faction_id="alliance")

        layer = EntitiesLayer([knight, ally])

        def query_fn(target: str, query: Query) -> Answer:
            if target == "politics" and query.question == QueryType.FACTION_RELATION:
                return Answer(value=FactionRelation.FRIENDLY)
            return Answer(value=None)

        nearby = layer.build_nearby_entities(knight, hour=12, query_fn=query_fn)
        assert len(nearby) == 1
        assert nearby[0].is_hostile is False


class TestSneakAttackAllyUsesSides:
    """Sneak attack ally adjacency uses combat sides, not faction queries."""

    def test_same_side_ally_enables_sneak_attack(self) -> None:
        """Guard on same side as rogue, adjacent to target → sneak attack triggers."""
        rogue = Character(
            id="rogue",
            name="Rogue",
            location_id="arena",
            faction_id="guards",
            in_combat=True,
            max_hp=20,
            current_hp=20,
            attacks=(_DAGGER_FINESSE,),
            ability_scores=_scores(DEX=16),
            class_features=[RogueFeatures(sneak_attack_dice=1)],
        )
        guard = Character(
            id="guard",
            name="Guard",
            location_id="arena",
            faction_id="guards",
            in_combat=True,
            max_hp=20,
            current_hp=20,
        )
        goblin = Character(
            id="goblin",
            name="Goblin",
            location_id="arena",
            faction_id="goblins",
            in_combat=True,
            max_hp=100,
            current_hp=100,
            ac=5,
        )

        layer = EntitiesLayer([rogue, guard, goblin])
        _setup_combat(
            layer,
            "arena",
            {"rogue": (10, 10), "guard": (20, 10), "goblin": (15, 10)},
            sides={0: {"rogue", "guard"}, 1: {"goblin"}},
            entity_to_side={"rogue": 0, "guard": 0, "goblin": 1},
        )

        sneak_attack_triggered = False
        for seed in range(100):
            goblin.current_hp = 100
            random.seed(seed)
            layer._combat._sneak_attack_used.clear()
            event = Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "rogue", "target_id": "goblin"},
            )
            layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

            for log_event in layer._combat._location_log["arena"]:
                if log_event.event_type == EventType.ENTITY_ATTACK and log_event.data.get("attacker_id") == "rogue":
                    components = log_event.data.get("damage_components", [])
                    for comp in components:
                        if isinstance(comp, dict) and comp.get("source") == "sneak_attack":
                            sneak_attack_triggered = True
                            break
            if sneak_attack_triggered:
                break

        assert sneak_attack_triggered, "Sneak attack should trigger with ally adjacent on same side"

    def test_different_side_not_ally_for_sneak_attack(self) -> None:
        """Bandit on different side, adjacent to target → does NOT count as ally for SA."""
        rogue = Character(
            id="rogue",
            name="Rogue",
            location_id="arena",
            faction_id="guards",
            in_combat=True,
            max_hp=20,
            current_hp=20,
            attacks=(_DAGGER_FINESSE,),
            ability_scores=_scores(DEX=16),
            class_features=[RogueFeatures(sneak_attack_dice=1)],
        )
        bandit = Character(
            id="bandit",
            name="Bandit",
            location_id="arena",
            faction_id="bandits",
            in_combat=True,
            max_hp=20,
            current_hp=20,
        )
        goblin = Character(
            id="goblin",
            name="Goblin",
            location_id="arena",
            faction_id="goblins",
            in_combat=True,
            max_hp=100,
            current_hp=100,
            ac=5,
        )

        layer = EntitiesLayer([rogue, bandit, goblin])
        _setup_combat(
            layer,
            "arena",
            {"rogue": (10, 10), "bandit": (20, 10), "goblin": (15, 10)},
            # All on different sides — bandit is NOT rogue's ally
            sides={0: {"rogue"}, 1: {"bandit"}, 2: {"goblin"}},
            entity_to_side={"rogue": 0, "bandit": 1, "goblin": 2},
        )

        sneak_attack_from_ally = False
        for seed in range(100):
            goblin.current_hp = 100
            random.seed(seed)
            layer._combat._sneak_attack_used.clear()
            layer._combat._location_log["arena"].clear()
            event = Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "rogue", "target_id": "goblin"},
            )
            layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

            for log_event in layer._combat._location_log["arena"]:
                if log_event.event_type == EventType.ENTITY_ATTACK and log_event.data.get("attacker_id") == "rogue":
                    components = log_event.data.get("damage_components", [])
                    for comp in components:
                        if isinstance(comp, dict) and comp.get("source") == "sneak_attack":
                            sneak_attack_from_ally = True
                            break

        # SA should never trigger — no ally adjacent, no advantage
        assert not sneak_attack_from_ally, "Sneak attack should NOT trigger without ally on same side"
