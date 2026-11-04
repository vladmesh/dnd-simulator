"""Round edge cases exercised with real worlds, dispatchers, and scripted decisions."""

from __future__ import annotations

import random
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from test_dead_creature_mid_turn import _ScriptedBrain
from test_game_loop import _make_world
from test_initiative import _FixedD20

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.character import Creature, DamageComponent, DamageType
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.events import TurnSkippedPayload
from dnd_simulator.core.intent import IntentType, TimedIntent, TravelIntent
from dnd_simulator.core.items import Item, ItemType, WeaponCategory, WeaponDef
from dnd_simulator.core.location import Location, LocationEdge, LocationGraph
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.round import Round, RoundResult


class _RecordingBrain(_ScriptedBrain):
    def __init__(self, actions: list[Action]) -> None:
        super().__init__(actions)
        self.awareness: list[PeacefulAwareness | CombatAwareness] = []

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        self.awareness.append(awareness)
        return super().choose_action(creature, awareness, events)


class _OpportunityBrain(_RecordingBrain):
    def choose_reaction(self, creature: Creature, trigger: ReactionTrigger, options: list[ReactionOption]) -> Action:
        option = options[0]
        return Action(name=option.action_type, params=option.params)


def _world(creatures: list[Creature]) -> tuple[World, EntitiesLayer]:
    template = _make_world([])
    host = EntitiesLayer(entities=list(creatures), seed=0, dice_rng=_FixedD20(20, seed=0))
    world = World(
        layers=[layer for layer in template.layers if not isinstance(layer, EntitiesLayer)] + [host],
        time=template.time,
        location_graph=template.location_graph,
        seed=0,
    )
    return world, host


def _combat(host: EntitiesLayer, creatures: list[Creature]) -> CombatState:
    combat = CombatState(
        location_id="r1", turn_order=[c.id for c in creatures], battle_map=BattleMap(width=60, height=60)
    )
    for index, creature in enumerate(creatures):
        creature.in_combat = True
        combat.battle_map.set_position(creature.id, Position(20 + index * 20, 20))
    host._combat._combats["r1"] = combat
    return combat


def _turn(game_round: Round, creature: Creature, world: World, *, resume_started: bool = False) -> list[Action]:
    return game_round.run_creature_turn(
        creature,
        world.time,
        world.make_query_fn("entities"),
        world.make_emit_fn("entities"),
        resume_started=resume_started,
    )


@pytest.mark.parametrize("grants", [(), (ActionType.BLESS,)])
def test_combat_setup_preserves_weapon_and_applies_condition_speed(grants: tuple[ActionType, ...]) -> None:
    brain = _RecordingBrain([END_TURN])
    actor = Creature(
        id="actor",
        name="Actor",
        location_id="r1",
        brain=brain,
        is_disengaging=True,
        conditions={Condition.GRAPPLED: None, Condition.BLINDED: 1},
    )
    actor.equipped_weapon = Item(
        id="staff",
        name="Staff",
        item_type=ItemType.WEAPON,
        weapon_def=WeaponDef(
            weapon_id="staff",
            attack_name="staff strike",
            category=WeaponCategory.SIMPLE,
            damage=(DamageComponent("1d4", DamageType.BLUDGEONING),),
            grant_actions=grants,
        ),
    )
    world, host = _world([actor])
    _combat(host, [actor])

    assert _turn(Round(world, rng=random.Random(0)), actor, world) == []

    assert actor.conditions == {Condition.GRAPPLED: None}
    assert actor.turn_budget == TurnBudget(movement_remaining=0)
    assert not actor.is_disengaging
    assert len(brain.awareness) == 1
    awareness = brain.awareness[0]
    assert isinstance(awareness, CombatAwareness)
    assert awareness.self_weapon == "staff strike"
    assert awareness.turn_budget is actor.turn_budget
    assert {item.item_id for item in awareness.equipped} == {"staff"}


def test_incapacitated_turn_ticks_conditions_and_emits_sorted_reasons() -> None:
    brain = _RecordingBrain([Action(name=ActionType.DODGE)])
    actor = Creature(
        id="actor",
        name="Actor",
        location_id="r1",
        brain=brain,
        conditions={Condition.STUNNED: None, Condition.PARALYZED: 3, Condition.BLINDED: 1},
    )
    world, host = _world([actor])
    _combat(host, [actor])
    emitted: list[Event] = []
    emit = world.make_emit_fn("entities")

    def record(event: Event) -> ActionResult:
        emitted.append(event)
        return emit(event)

    actions = Round(world, rng=random.Random(0)).run_creature_turn(
        actor, world.time, world.make_query_fn("entities"), record
    )

    assert actions == []
    assert brain.awareness == []
    assert actor.turn_budget is None
    assert actor.conditions == {Condition.STUNNED: None, Condition.PARALYZED: 2}
    assert [event.payload for event in emitted if event.event_type == EventType.TURN_SKIPPED] == [
        TurnSkippedPayload(actor.id, "incapacitated", ("paralyzed", "stunned"), "r1")
    ]


@pytest.mark.parametrize("in_combat", [False, True])
def test_brainless_creature_has_no_turn_side_effects(in_combat: bool) -> None:
    actor = Creature(id="actor", name="Actor", location_id="r1", conditions={Condition.BLINDED: 2})
    world, host = _world([actor])
    if in_combat:
        _combat(host, [actor])

    assert _turn(Round(world, rng=random.Random(0)), actor, world) == []
    assert actor.turn_budget is None
    assert actor.conditions == {Condition.BLINDED: 2}


def test_dead_peaceful_creature_is_not_prompted() -> None:
    brain = _RecordingBrain([Action(name=ActionType.WAIT)])
    actor = Creature(id="actor", name="Actor", location_id="r1", current_hp=0, brain=brain)
    world, _host = _world([actor])

    assert _turn(Round(world, rng=random.Random(0)), actor, world) == []
    assert brain.awareness == []
    assert actor.current_intent is None


@pytest.mark.parametrize(("relation", "expected_x"), [("toward", 25), ("away_from", 15)])
def test_abstract_combat_move_resolves_direction_and_spends_movement(relation: str, expected_x: int) -> None:
    brain = _RecordingBrain([Action(name=ActionType.MOVE, params={relation: "foe", "ft": 5}), END_TURN])
    actor = Creature(id="actor", name="Actor", location_id="r1", brain=brain)
    foe = Creature(id="foe", name="Foe", location_id="r1")
    world, host = _world([actor, foe])
    combat = _combat(host, [actor, foe])

    actions = _turn(Round(world, rng=random.Random(0)), actor, world)

    direction = "east" if relation == "toward" else "west"
    assert actions == [Action(name=ActionType.MOVE, params={"direction": direction, "ft": 5})]
    assert combat.battle_map.get_position(actor.id) == Position(expected_x, 20)
    assert actor.turn_budget is not None
    assert actor.turn_budget.movement_remaining == 25
    assert len(brain.awareness) == 2


def test_resumed_turn_ends_when_last_resource_is_spent_without_reticking_conditions() -> None:
    brain = _RecordingBrain([Action(name=ActionType.DODGE), Action(name=ActionType.DASH)])
    budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=0, reaction=0)
    actor = Creature(
        id="actor",
        name="Actor",
        location_id="r1",
        brain=brain,
        turn_budget=budget,
        conditions={Condition.GRAPPLED: 3},
    )
    world, host = _world([actor])
    _combat(host, [actor])

    actions = _turn(Round(world, rng=random.Random(0)), actor, world, resume_started=True)

    assert actions == [Action(name=ActionType.DODGE)]
    assert actor.is_dodging
    assert actor.turn_budget is budget
    assert budget == TurnBudget(actions=0, bonus_actions=0, movement_remaining=0, reaction=0)
    assert actor.conditions == {Condition.GRAPPLED: 3, Condition.DODGING: 1}
    assert len(brain.awareness) == 1


def test_travel_after_external_combat_removal_ends_turn_without_another_prompt() -> None:
    brain = _RecordingBrain(
        [Action(name=ActionType.DODGE), Action(name=ActionType.TRAVEL, params={"destination_id": "road"})]
    )
    actor = Creature(id="actor", name="Actor", location_id="r1", brain=brain, is_anchor=True)
    foe = Creature(id="foe", name="Foe", location_id="r1")
    world, host = _world([actor, foe])
    world.location_graph = LocationGraph(
        [Location("r1", "Field", "r1", edges=(LocationEdge("road", 1000),)), Location("road", "Road", "r1")]
    )
    _combat(host, [actor, foe])
    game_round = Round(world, rng=random.Random(0))

    def remove_after_dodge(creature: Creature, action: Action, budget: TurnBudget | None, error: str) -> None:
        if action.name == ActionType.DODGE and not error:
            host.remove_from_combat(creature.id)

    game_round.set_on_action(remove_after_dodge)
    actions = _turn(game_round, actor, world)

    assert [action.name for action in actions] == [ActionType.DODGE, ActionType.TRAVEL]
    assert len(brain.awareness) == 2
    assert isinstance(brain.awareness[1], PeacefulAwareness)
    assert isinstance(actor.current_intent, TravelIntent)
    assert actor.current_intent.destination_id == "road"
    assert not actor.active
    assert host.get_active_combat_for(actor.id) is None


def test_lethal_opportunity_attack_prevents_later_reactors_and_movement() -> None:
    mover = Creature(
        id="mover",
        name="Mover",
        location_id="r1",
        current_hp=1,
        brain=_RecordingBrain([Action(name=ActionType.MOVE, params={"direction": "west", "ft": 5})]),
    )
    first = Creature(id="first", name="First", location_id="r1", brain=_OpportunityBrain([]), turn_budget=TurnBudget())
    second = Creature(
        id="second", name="Second", location_id="r1", brain=_OpportunityBrain([]), turn_budget=TurnBudget()
    )
    world, host = _world([mover, first, second])
    combat = _combat(host, [mover, first, second])
    combat.battle_map.set_position(first.id, Position(25, 20))
    combat.battle_map.set_position(second.id, Position(25, 25))

    actions = _turn(Round(world, rng=random.Random(0)), mover, world)

    assert [action.name for action in actions] == [ActionType.MOVE]
    assert mover.current_hp == 0
    assert mover.turn_budget is not None
    assert mover.turn_budget.movement_remaining == 30
    assert first.turn_budget is not None
    assert first.turn_budget.reaction == 0
    assert second.turn_budget == TurnBudget()
    assert combat.battle_map.get_position(mover.id) != Position(15, 20)


def test_stop_after_last_peaceful_action_does_not_advance_time() -> None:
    actor = Creature(
        id="actor",
        name="Actor",
        location_id="r1",
        is_anchor=True,
        brain=_RecordingBrain([Action(name=ActionType.WAIT)]),
    )
    world, _host = _world([actor])
    initial = world.time
    game_round = Round(world, rng=random.Random(0))

    def stop_after_action(creature: Creature, action: Action, budget: TurnBudget | None, error: str) -> None:
        game_round.stop()

    game_round.set_on_action(stop_after_action)
    result = game_round.run_round()

    assert result.interrupted and result.should_stop
    assert world.time == initial
    assert not actor.active
    assert isinstance(actor.current_intent, TimedIntent)
    assert actor.current_intent.wake_at_seconds == initial.to_total_seconds() + 3600


@pytest.mark.parametrize("started", [False, True])
def test_stop_before_resumed_combat_turn_preserves_cursor_and_state(started: bool) -> None:
    brain = _RecordingBrain([Action(name=ActionType.DODGE)])
    actor = Creature(id="actor", name="Actor", location_id="r1", brain=brain, conditions={Condition.BLINDED: 2})
    world, host = _world([actor])
    combat = _combat(host, [actor])
    combat.resume_turn_index = 0
    combat.resume_turn_started = started
    budget = TurnBudget(actions=0, movement_remaining=10)
    actor.turn_budget = budget
    game_round = Round(world, rng=random.Random(0))
    initial = world.time
    game_round.stop()

    result = game_round.run_round()

    assert result.interrupted and result.should_stop
    assert world.time == initial
    assert combat.resume_turn_index == 0
    assert combat.resume_turn_started is started
    assert combat.round_number == 1
    assert actor.turn_budget is budget
    assert actor.conditions == {Condition.BLINDED: 2}
    assert brain.awareness == []


def test_round_end_callback_can_request_natural_loop_completion() -> None:
    brain = _RecordingBrain([END_TURN])
    actor = Creature(id="actor", name="Actor", location_id="r1", brain=brain, is_anchor=True)
    world, _host = _world([actor])
    initial = world.time.to_total_seconds()
    game_round = Round(world, rng=random.Random(0))
    results: list[RoundResult] = []

    def finish(result: RoundResult) -> None:
        results.append(result)
        result.should_stop = True

    game_round.set_on_round_end(finish)
    game_round.run_loop(max_rounds=3)

    assert len(results) == 1
    assert not results[0].interrupted
    assert not game_round.is_stopped
    assert len(brain.awareness) == 1
    assert world.time.to_total_seconds() == initial + 6


@pytest.mark.parametrize("overdue_seconds", [0, 10])
def test_expired_wait_inserted_between_activation_and_fast_forward_wakes_without_time_jump(
    overdue_seconds: int,
) -> None:
    """A mutation-gate boundary can admit an already-due GM intent after activation."""
    brain = _RecordingBrain([END_TURN])
    actor = Creature(id="actor", name="Actor", location_id="r1", brain=brain, is_anchor=True)
    world, host = _world([actor])
    initial = world.time.to_total_seconds()
    insert_wait = True

    @contextmanager
    def mutation_scope() -> Iterator[None]:
        nonlocal insert_wait
        yield
        if insert_wait:
            insert_wait = False
            actor.current_intent = TimedIntent(IntentType.WAIT, initial - 60, initial - overdue_seconds)
            host.dormify(actor)

    results: list[RoundResult] = []
    game_round = Round(world, rng=random.Random(0), mutation_scope=mutation_scope)
    game_round.set_on_round_end(results.append)
    game_round.run_loop(max_rounds=1)

    assert actor.active
    assert actor.current_intent is None
    assert len(brain.awareness) == 1
    assert len(results) == 1
    assert world.time.to_total_seconds() == initial + 6
