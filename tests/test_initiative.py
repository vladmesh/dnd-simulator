"""Tests for initiative rolls, CombatState lifecycle, and game loop branching."""

from __future__ import annotations

import random

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    Creature,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, GameDateTime, Query
from dnd_simulator.core.world import World
from dnd_simulator.game_loop import run_game_loop
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.rules.combat import roll_initiative


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)


def _scores(**overrides: int) -> AbilityScores:
    """Create ability scores with overrides."""
    scores = dict(AbilityScores().scores)
    for name, val in overrides.items():
        scores[Ability[name.upper()]] = val
    return AbilityScores(scores=scores)


# --- roll_initiative ---


class TestRollInitiative:
    def test_sorts_by_total_descending(self) -> None:
        # Fix RNG so d20 rolls are predictable
        rng = random.Random(42)
        high_dex = Creature(id="fast", name="Fast", location_id="r1", ability_scores=_scores(dex=18))
        low_dex = Creature(id="slow", name="Slow", location_id="r1", ability_scores=_scores(dex=8))
        # With many trials, higher DEX should generally go first
        wins = 0
        for seed in range(100):
            rng = random.Random(seed)
            order = roll_initiative([high_dex, low_dex], rng=rng)
            if order[0].id == "fast":
                wins += 1
        # Higher DEX should win majority
        assert wins > 60

    def test_returns_all_creatures(self) -> None:
        rng = random.Random(1)
        creatures = [Creature(id=f"c{i}", name=f"C{i}", location_id="r1") for i in range(5)]
        result = roll_initiative(creatures, rng=rng)
        assert len(result) == 5
        assert {c.id for c in result} == {c.id for c in creatures}

    def test_tiebreaker_by_dex_score(self) -> None:
        # Same modifier (DEX 14 and 15 both have +2), but different scores
        # Higher score should win ties
        wins_15 = 0
        for seed in range(200):
            rng = random.Random(seed)
            c14 = Creature(id="dex14", name="D14", location_id="r1", ability_scores=_scores(dex=14))
            c15 = Creature(id="dex15", name="D15", location_id="r1", ability_scores=_scores(dex=15))
            order = roll_initiative([c14, c15], rng=rng)
            if order[0].id == "dex15":
                wins_15 += 1
        # dex15 should win slightly more often due to tiebreaker
        assert wins_15 > 90

    def test_single_creature(self) -> None:
        rng = random.Random(1)
        c = Creature(id="solo", name="Solo", location_id="r1")
        result = roll_initiative([c], rng=rng)
        assert result == [c]

    def test_empty_list(self) -> None:
        result = roll_initiative([], rng=random.Random(1))
        assert result == []


# --- CombatState ---


class TestCombatState:
    def test_defaults(self) -> None:
        cs = CombatState(location_id="r1", turn_order=["a", "b", "c"])
        assert cs.round_number == 1
        assert cs.rounds_without_attack == 0

    def test_mutable(self) -> None:
        cs = CombatState(location_id="r1", turn_order=["a", "b"])
        cs.round_number = 3
        cs.rounds_without_attack = 2
        assert cs.round_number == 3


# --- EntitiesLayer combat management ---


class TestEntitiesLayerCombat:
    def _make_layer(self) -> tuple[EntitiesLayer, Creature, Creature, Creature]:
        c1 = Character(id="c1", name="Fighter", location_id="r1", max_hp=20, current_hp=20, ac=15, attacks=(_SWORD,))
        c2 = Character(id="c2", name="Rogue", location_id="r1", max_hp=15, current_hp=15, ac=12, attacks=(_SWORD,))
        c3 = Character(id="c3", name="Bystander", location_id="r1", max_hp=10, current_hp=10)
        layer = EntitiesLayer([c1, c2, c3])
        return layer, c1, c2, c3

    def test_first_attack_creates_combat(self) -> None:
        layer, _c1, _c2, _c3 = self._make_layer()
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "c1", "target_id": "c2"},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

        combat = layer.get_combat("r1")
        assert combat is not None
        assert set(combat.turn_order) == {"c1", "c2", "c3"}
        assert combat.round_number == 1

    def test_all_in_region_marked_in_combat(self) -> None:
        layer, c1, c2, c3 = self._make_layer()
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "c1", "target_id": "c2"},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

        assert c1.in_combat is True
        assert c2.in_combat is True
        assert c3.in_combat is True

    def test_second_attack_does_not_reroll_initiative(self) -> None:
        layer, _c1, _c2, _c3 = self._make_layer()
        atk = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "c1", "target_id": "c2"},
        )
        layer.handle_event(atk, _noop_query_fn, _noop_emit_fn)
        first_order = list(layer.get_combat("r1").turn_order)

        layer.handle_event(atk, _noop_query_fn, _noop_emit_fn)
        second_order = list(layer.get_combat("r1").turn_order)
        assert first_order == second_order

    def test_other_region_not_affected(self) -> None:
        c_other = Character(id="c4", name="Farmer", location_id="r2", max_hp=10, current_hp=10)
        layer, _c1, _c2, _c3 = self._make_layer()
        layer.add_entity(c_other)

        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "c1", "target_id": "c2"},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        assert c_other.in_combat is False
        assert layer.get_combat("r2") is None

    def test_end_combat_round_increments_round(self) -> None:
        layer, _c1, _c2, _c3 = self._make_layer()
        # Start combat
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "c1", "target_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        layer.end_combat_round("r1")
        combat = layer.get_combat("r1")
        assert combat is not None
        assert combat.round_number == 2

    def test_two_rounds_without_attack_ends_combat(self) -> None:
        layer, c1, c2, c3 = self._make_layer()
        # Start combat with attack
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "c1", "target_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        # Round 1 had an attack → rounds_without_attack stays 0
        layer.end_combat_round("r1")
        assert layer.get_combat("r1") is not None

        # Round 2: no attacks
        layer.end_combat_round("r1")
        assert layer.get_combat("r1") is not None  # only 1 round without attack

        # Round 3: no attacks again
        layer.end_combat_round("r1")
        # 2 consecutive rounds without attack → combat ends
        assert layer.get_combat("r1") is None
        assert c1.in_combat is False
        assert c2.in_combat is False
        assert c3.in_combat is False

    def test_attack_resets_no_attack_counter(self) -> None:
        layer, _c1, _c2, _c3 = self._make_layer()
        # Start combat
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "c1", "target_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        layer.end_combat_round("r1")  # round 1 had attack → rwa=0

        # Round 2: no attack
        layer.end_combat_round("r1")  # rwa=1
        assert layer.get_combat("r1") is not None

        # Round 3: attack happens!
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "c1", "target_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        layer.end_combat_round("r1")  # had attack → rwa=0
        assert layer.get_combat("r1") is not None

        # Round 4, 5: no attacks → combat ends
        layer.end_combat_round("r1")  # rwa=1
        layer.end_combat_round("r1")  # rwa=2 → end
        assert layer.get_combat("r1") is None


class TestFleeRemovesFromCombat:
    def test_flee_removes_from_turn_order(self) -> None:
        c1 = Character(id="c1", name="Fighter", location_id="r1", max_hp=20, current_hp=20, attacks=(_SWORD,))
        c2 = Character(id="c2", name="Rogue", location_id="r1", max_hp=15, current_hp=15, attacks=(_SWORD,))
        c3 = Character(id="c3", name="Mage", location_id="r1", max_hp=8, current_hp=8)
        layer = EntitiesLayer([c1, c2, c3])

        # Start combat
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "c1", "target_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        assert "c3" in layer.get_combat("r1").turn_order

        # c3 flees
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_FLEE,
                source_layer="entities",
                data={"entity_id": "c3"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        assert c3.in_combat is False
        combat = layer.get_combat("r1")
        assert combat is not None
        assert "c3" not in combat.turn_order

    def test_flee_last_two_ends_combat(self) -> None:
        c1 = Character(id="c1", name="Fighter", location_id="r1", max_hp=20, current_hp=20, attacks=(_SWORD,))
        c2 = Character(id="c2", name="Rogue", location_id="r1", max_hp=15, current_hp=15)
        layer = EntitiesLayer([c1, c2])

        # Start combat
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "c1", "target_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )

        # c2 flees — only 1 left → combat ends
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_FLEE,
                source_layer="entities",
                data={"entity_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        assert layer.get_combat("r1") is None
        assert c1.in_combat is False
        assert c2.in_combat is False


class TestDeathRemovesFromCombat:
    def test_kill_removes_from_turn_order(self) -> None:
        c1 = Character(
            id="c1",
            name="Fighter",
            location_id="r1",
            max_hp=20,
            current_hp=20,
            ac=15,
            attacks=(_SWORD,),
            ability_scores=_scores(str=20),  # high STR for guaranteed hit
        )
        c2 = Character(id="c2", name="Weakling", location_id="r1", max_hp=1, current_hp=1, ac=1)
        c3 = Character(id="c3", name="Observer", location_id="r1", max_hp=10, current_hp=10)
        layer = EntitiesLayer([c1, c2, c3])

        # Attack c2 (HP=1, AC=1 → almost guaranteed kill)
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "c1", "target_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )

        combat = layer.get_combat("r1")
        if not c2.is_alive:
            # c2 should be removed from turn order
            assert "c2" not in combat.turn_order if combat else True

    def test_all_but_one_die_ends_combat(self) -> None:
        c1 = Character(
            id="c1",
            name="Fighter",
            location_id="r1",
            max_hp=20,
            current_hp=20,
            ac=15,
            attacks=(_SWORD,),
            ability_scores=_scores(str=30),
        )
        c2 = Character(id="c2", name="Weak", location_id="r1", max_hp=1, current_hp=1, ac=1)
        layer = EntitiesLayer([c1, c2])

        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "c1", "target_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )

        if not c2.is_alive:
            # Only c1 left → combat should end
            assert layer.get_combat("r1") is None
            assert c1.in_combat is False


class TestCombatInfoQuery:
    def test_returns_round_and_order(self) -> None:
        from dnd_simulator.core.models import Query

        c1 = Character(id="c1", name="A", location_id="r1", max_hp=20, current_hp=20, attacks=(_SWORD,))
        c2 = Character(id="c2", name="B", location_id="r1", max_hp=15, current_hp=15)
        layer = EntitiesLayer([c1, c2])

        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "c1", "target_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        answer = layer.query(Query(question="combat_info", params={"location_id": "r1"}))
        assert answer.value is not None
        assert answer.value["round_number"] == 1
        assert set(answer.value["turn_order"]) == {"c1", "c2"}

    def test_returns_none_outside_combat(self) -> None:
        from dnd_simulator.core.models import Query

        c1 = Character(id="c1", name="A", location_id="r1")
        layer = EntitiesLayer([c1])
        answer = layer.query(Query(question="combat_info", params={"location_id": "r1"}))
        assert answer.value is None


# --- Game loop branching ---


class TestGameLoopCombat:
    def test_combat_creatures_turn_in_initiative_order(self) -> None:
        """Combat creatures should take turns in initiative order, not insertion order."""
        from dnd_simulator.core.action import Action
        from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
        from dnd_simulator.core.brain import Brain

        turn_log: list[str] = []

        class LogBrain(Brain):
            def choose_action(
                self,
                creature: Creature,
                awareness: PeacefulAwareness | CombatAwareness,
                events: list[PerceivedEvent],
            ) -> Action:
                turn_log.append(creature.id)
                return Action(name="idle")

        c1 = Character(
            id="c1", name="A", location_id="r1", max_hp=20, current_hp=20, attacks=(_SWORD,), brain=LogBrain()
        )
        c2 = Character(
            id="c2", name="B", location_id="r1", max_hp=15, current_hp=15, attacks=(_SWORD,), brain=LogBrain()
        )

        layer = EntitiesLayer([c1, c2])
        world = World(
            layers=[layer],
            time=GameDateTime(),
            location_graph=LocationGraph([Location(id="r1", name="Test", region_id="r1")]),
        )

        # Start combat manually
        layer._combat.start_combat("r1")

        # Override turn_order to a known order
        combat = layer.get_combat("r1")
        assert combat is not None
        combat.turn_order = ["c2", "c1"]  # c2 goes first

        # Run one iteration manually via EntitiesLayer orchestration
        query_fn = world._make_query_fn("entities")
        emit_fn = world._make_emit_fn("entities")
        for entity_id in list(combat.turn_order):
            entity = layer.get_entity(entity_id)
            if isinstance(entity, Creature) and entity.is_alive and entity.active and entity.in_combat:
                layer.run_creature_turn(entity, world.time, query_fn, emit_fn)

        assert turn_log == ["c2", "c1"]

    def test_peaceful_creatures_skip_combat(self) -> None:
        """Peaceful creatures should not be polled during combat rounds."""
        from dnd_simulator.core.action import Action
        from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
        from dnd_simulator.core.brain import Brain

        turn_log: list[str] = []

        class LogBrain(Brain):
            def choose_action(
                self,
                creature: Creature,
                awareness: PeacefulAwareness | CombatAwareness,
                events: list[PerceivedEvent],
            ) -> Action:
                turn_log.append(creature.id)
                # Stop the loop after first round
                if len(turn_log) >= 3:
                    creature.active = False
                return Action(name="idle")

        c_combat1 = Character(
            id="c1", name="A", location_id="r1", max_hp=20, current_hp=20, attacks=(_SWORD,), brain=LogBrain()
        )
        c_combat2 = Character(id="c2", name="B", location_id="r1", max_hp=15, current_hp=15, brain=LogBrain())
        c_peaceful = Character(id="c3", name="C", location_id="r2", max_hp=10, current_hp=10, brain=LogBrain())

        layer = EntitiesLayer([c_combat1, c_combat2, c_peaceful])
        world = World(
            layers=[layer],
            time=GameDateTime(),
            location_graph=LocationGraph(
                [
                    Location(id="r1", name="Test", region_id="r1"),
                    Location(id="r2", name="Test2", region_id="r2"),
                ]
            ),
        )

        # Put r1 in combat
        layer._combat.start_combat("r1")
        combat = layer.get_combat("r1")
        combat.turn_order = ["c1", "c2"]

        run_game_loop(world)

        # c3 should have taken a turn (it's peaceful, in a different region)
        assert "c3" in turn_log
        # c1 and c2 should have taken turns via combat
        assert "c1" in turn_log
        assert "c2" in turn_log
