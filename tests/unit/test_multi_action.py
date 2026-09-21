"""Tests for multi-action turn loop, TurnBudget, and action cost enforcement."""

from __future__ import annotations

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.intent import TravelIntent
from dnd_simulator.core.location import Location, LocationEdge, LocationGraph
from dnd_simulator.core.models import EventType, GameDateTime
from dnd_simulator.core.turn_budget import ActionCost, TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.round import Round
from dnd_simulator.rules.actions import action_cost


def _make_world(entities: list[Creature]) -> World:
    region = Region(
        id="r1",
        name="Field",
        terrain=TerrainType.PLAINS,
        latitude=45.0,
        longitude=0.0,
        elevation=100,
        water_proximity=0.0,
        connections=[],
    )
    geography = GeographyLayer(regions=[region])
    settlements = SettlementsLayer(settlements=[], region_terrains={"r1": TerrainType.PLAINS})
    politics = PoliticsLayer(
        nations=[],
        region_terrains={"r1": TerrainType.PLAINS},
        region_adjacency={},
        region_income_fn=settlements.get_region_income,
    )
    entities_layer = EntitiesLayer(entities=list(entities))
    return World(
        layers=[geography, politics, settlements, entities_layer],
        time=GameDateTime(year=1, month=1, day=1, hour=10),
        location_graph=LocationGraph([Location(id="r1", name="Field", region_id="r1")]),
    )


# -- TurnBudget unit tests --


class TestTurnBudget:
    def test_can_afford_exact(self) -> None:
        budget = TurnBudget(actions=1, bonus_actions=1, movement_remaining=30)
        assert budget.can_afford(ActionCost(actions=1))
        assert budget.can_afford(ActionCost(bonus_actions=1))
        assert budget.can_afford(ActionCost(movement_ft=30))

    def test_cannot_afford_over(self) -> None:
        budget = TurnBudget(actions=0, bonus_actions=1, movement_remaining=10)
        assert not budget.can_afford(ActionCost(actions=1))
        assert not budget.can_afford(ActionCost(movement_ft=15))

    def test_consume_deducts(self) -> None:
        budget = TurnBudget(actions=2, bonus_actions=1, movement_remaining=30)
        budget.consume(ActionCost(actions=1))
        assert budget.actions == 1
        budget.consume(ActionCost(movement_ft=15))
        assert budget.movement_remaining == 15

    def test_consume_raises_on_insufficient(self) -> None:
        budget = TurnBudget(actions=0)
        import pytest

        with pytest.raises(ValueError, match="Insufficient budget"):
            budget.consume(ActionCost(actions=1))

    def test_turn_over(self) -> None:
        budget = TurnBudget(actions=0, bonus_actions=0, movement_remaining=0)
        assert budget.turn_over

    def test_turn_not_over(self) -> None:
        budget = TurnBudget(actions=0, bonus_actions=0, movement_remaining=5)
        assert not budget.turn_over


# -- Action cost tests --


class TestActionCost:
    def test_attack_costs_one_action(self) -> None:
        cost = action_cost(Action(name=ActionType.ATTACK, params={"target_id": "x"}))
        assert cost.actions == 1
        assert cost.bonus_actions == 0

    def test_idle_is_free(self) -> None:
        cost = action_cost(Action(name=ActionType.IDLE))
        assert cost.actions == 0 and cost.bonus_actions == 0 and cost.movement_ft == 0

    def test_end_turn_is_free(self) -> None:
        cost = action_cost(END_TURN)
        assert cost.actions == 0

    def test_say_is_free(self) -> None:
        cost = action_cost(Action(name=ActionType.SAY, params={"text": "hi"}))
        assert cost.actions == 0

    def test_dodge_costs_one_action(self) -> None:
        cost = action_cost(Action(name=ActionType.DODGE))
        assert cost.actions == 1

    def test_move_is_free_at_dispatcher(self) -> None:
        # MOVE is cost_type=FREE: handle_move charges the distance walked directly, so the
        # dispatcher-level cost carries no movement (avoids double-counting with the handler).
        cost = action_cost(Action(name=ActionType.MOVE, params={"toward": "x"}))
        assert cost.movement_ft == 0
        assert cost.actions == 0 and cost.bonus_actions == 0 and cost.reaction == 0


# -- Multi-action loop integration tests --


class _ScriptedBrain(Brain):
    """Brain that plays a scripted sequence of actions."""

    def __init__(self, actions: list[Action]) -> None:
        self._actions = list(actions)
        self._index = 0

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        if self._index >= len(self._actions):
            return END_TURN
        action = self._actions[self._index]
        self._index += 1
        return action


class TestMultiActionLoop:
    def test_missing_param_does_not_spend_budget_and_next_action_runs(self) -> None:
        brain = _ScriptedBrain(
            [
                Action(name=ActionType.ATTACK, params={}),
                Action(name=ActionType.DODGE),
                END_TURN,
            ]
        )
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain, in_combat=True)

        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        el._combat._combats["r1"] = CombatState(location_id="r1", turn_order=[creature.id])
        game_round = Round(world, el)
        callback_log: list[tuple[ActionType, int, str]] = []

        def on_action(c: Creature, a: Action, b: TurnBudget | None, error: str = "") -> None:
            assert b is not None
            callback_log.append((a.name, b.actions, error))

        game_round.set_on_action(on_action)
        actions = game_round.run_combat_turn(
            creature,
            world.time,
            world.make_query_fn("entities"),
            world.make_emit_fn("entities"),
        )

        assert [action.name for action in actions] == [ActionType.DODGE]
        assert callback_log[0][0] == ActionType.ATTACK
        assert callback_log[0][1] == 1
        assert callback_log[0][2]
        assert callback_log[1] == (ActionType.DODGE, 0, "")

    def test_single_action_then_end_turn(self) -> None:
        """Brain does one action then end_turn. Round records it."""
        brain = _ScriptedBrain([Action(name=ActionType.SAY, params={"text": "hi"}), END_TURN])
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain)
        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        actions = game_round.run_creature_turn(creature, world.time, query_fn, emit_fn)

        assert len(actions) == 1
        assert actions[0].name == ActionType.SAY

    def test_budget_exhaustion_ends_turn(self) -> None:
        """When budget runs out, turn ends even without end_turn.

        Uses dodge (always succeeds, costs 1 action) to reliably consume budget.
        """
        # Brain tries to dodge twice, but only has 1 action
        brain = _ScriptedBrain(
            [
                Action(name=ActionType.DODGE),
                Action(name=ActionType.DODGE),
            ]
        )
        creature = Creature(
            id="c1",
            name="A",
            location_id="r1",
            brain=brain,
            max_hp=20,
            current_hp=20,
            in_combat=True,
        )
        target = Creature(id="target1", name="T", location_id="r1", max_hp=100, current_hp=100)

        world = _make_world([creature, target])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        el._combat._combats["r1"] = CombatState(location_id="r1", turn_order=[creature.id, target.id])
        game_round = Round(world, el)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        actions = game_round.run_combat_turn(creature, world.time, query_fn, emit_fn)

        # Only 1 dodge should have executed (budget has 1 action)
        assert len(actions) == 1
        assert actions[0].name == ActionType.DODGE

    def test_on_action_callback_fires(self) -> None:
        """on_action callback fires after each action with current budget in combat."""
        brain = _ScriptedBrain([Action(name=ActionType.DODGE), END_TURN])
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain, in_combat=True)

        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        el._combat._combats["r1"] = CombatState(location_id="r1", turn_order=[creature.id])
        game_round = Round(world, el)

        callback_log: list[tuple[str, str, int]] = []

        def on_action(c: Creature, a: Action, b: TurnBudget | None, error: str = "") -> None:
            assert b is not None
            callback_log.append((c.id, a.name, b.actions))

        game_round.set_on_action(on_action)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        game_round.run_combat_turn(creature, world.time, query_fn, emit_fn)

        assert len(callback_log) == 1
        assert callback_log[0] == ("c1", ActionType.DODGE, 0)  # dodge costs 1 action

    def test_awareness_includes_budget_in_combat(self) -> None:
        """Combat awareness includes turn_budget."""
        received_budgets: list[TurnBudget | None] = []

        class BudgetCaptureBrain(Brain):
            def choose_action(
                self,
                creature: Creature,
                awareness: PeacefulAwareness | CombatAwareness,
                events: list[PerceivedEvent],
            ) -> Action:
                received_budgets.append(awareness.turn_budget)
                return END_TURN

        creature = Creature(id="c1", name="A", location_id="r1", brain=BudgetCaptureBrain(), in_combat=True)
        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        el._combat._combats["r1"] = CombatState(location_id="r1", turn_order=[creature.id])
        game_round = Round(world, el)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        game_round.run_combat_turn(creature, world.time, query_fn, emit_fn)

        assert len(received_budgets) == 1
        budget = received_budgets[0]
        assert budget is not None
        assert budget.actions == 1
        assert budget.bonus_actions == 1
        assert budget.movement_remaining == creature.speed

    def test_flee_then_travel_same_turn_uses_refreshed_combat_context(self) -> None:
        """Regression (dnd-simulator-265), updated for dnd-simulator-275.

        ``run_combat_turn`` builds one ``ActionContext`` before its multi-action loop.
        A synchronous ``flee`` can end a one-on-one combat and delete the ``CombatState``
        mid-loop; nothing in that turn may keep acting on the pre-flee snapshot. Since
        dnd-simulator-275 flee is itself the journey (one edge to a neighbour) and ends
        the fleer's turn, so the stale-context hazard is closed by never re-entering the
        loop: the scripted follow-up ``travel`` is never dispatched, and the journey the
        fleer is on is the flee's own. Also proves the flee path actually records
        ``EventType.COMBAT_ENDED`` in the entities location event log, not just that
        the in-memory ``CombatState`` disappeared.
        """
        brain = _ScriptedBrain(
            [
                Action(name=ActionType.FLEE, params={"description": "run"}),
                Action(name=ActionType.TRAVEL, params={"destination_id": "far"}),
                END_TURN,
            ]
        )
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain, in_combat=True)
        foe = Creature(id="foe", name="Foe", location_id="r1", in_combat=True)

        world = _make_world([creature, foe])
        world.location_graph = LocationGraph(
            [
                Location(id="r1", name="Field", region_id="r1", edges=(LocationEdge("goal", 1000),)),
                Location(id="goal", name="Goal", region_id="r1", edges=(LocationEdge("far", 1000),)),
                Location(id="far", name="Far", region_id="r1"),
            ]
        )
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        el._combat._combats["r1"] = CombatState(location_id="r1", turn_order=[creature.id, foe.id])
        game_round = Round(world, el)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        actions = game_round.run_combat_turn(creature, world.time, query_fn, emit_fn)

        # Flee ended the turn: the scripted travel was never dispatched.
        assert [a.name for a in actions] == [ActionType.FLEE]

        # Flee ended the final one-on-one combat: no authoritative combat membership remains.
        assert el._combat.get_active_combat_for(creature.id) is None
        assert el._combat.get_combat("r1") is None

        # The flee path actually recorded combat end in the entities location event
        # log (CombatManager._end_combat), not just removed the CombatState in memory.
        assert any(e.event_type == EventType.COMBAT_ENDED for e in el._combat._location_log["r1"])

        # The flee's own one-edge journey is the one under way, and the fleer is dormant.
        assert isinstance(creature.current_intent, TravelIntent)
        assert creature.current_intent.destination_id == "goal"
        assert creature.current_intent.remaining_route == ("goal",)
        assert creature.active is False

    def test_loop_stops_after_peaceful_turn_ending_action_post_flee(self) -> None:
        """After a successful flee the combat-turn loop stops cleanly: the brain is not
        consulted again this turn, so the fleer is never offered combat (or any) actions
        after leaving the scene — scripted follow-ups must never be dispatched.
        """
        brain = _ScriptedBrain(
            [
                Action(name=ActionType.FLEE, params={"description": "run"}),
                Action(name=ActionType.TRAVEL, params={"destination_id": "goal"}),  # must never be reached
                Action(name=ActionType.DODGE),  # must never be reached
            ]
        )
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain, in_combat=True)
        foe = Creature(id="foe", name="Foe", location_id="r1", in_combat=True)
        ally = Creature(id="ally", name="Ally", location_id="r1", in_combat=True)
        other_foe = Creature(id="foe2", name="Foe 2", location_id="r1", in_combat=True)

        world = _make_world([creature, foe, ally, other_foe])
        world.location_graph = LocationGraph(
            [
                Location(id="r1", name="Field", region_id="r1", edges=(LocationEdge("goal", 1000),)),
                Location(id="goal", name="Goal", region_id="r1"),
            ]
        )
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        el._combat._combats["r1"] = CombatState(
            location_id="r1",
            turn_order=[creature.id, foe.id, ally.id, other_foe.id],
            sides={0: {creature.id, ally.id}, 1: {foe.id, other_foe.id}},
            entity_to_side={creature.id: 0, ally.id: 0, foe.id: 1, other_foe.id: 1},
        )
        game_round = Round(world, el)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        actions = game_round.run_combat_turn(creature, world.time, query_fn, emit_fn)

        assert [a.name for a in actions] == [ActionType.FLEE]
        # The brain was consulted exactly once — nothing was offered after the flee.
        assert brain._index == 1
        # The fight goes on without the fleer.
        combat = el._combat.get_combat("r1")
        assert combat is not None
        assert creature.id not in combat.turn_order


# -- Peaceful turn tests --


class TestPeacefulTurn:
    def test_say_ends_peaceful_turn(self) -> None:
        """Say is a turn-ending action in peaceful mode."""
        brain = _ScriptedBrain([Action(name=ActionType.SAY, params={"text": "hi"})])
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain)

        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        actions = game_round.run_peaceful_turn(creature, world.time, query_fn, emit_fn)

        assert len(actions) == 1
        assert actions[0].name == ActionType.SAY

    def test_idle_ends_peaceful_turn(self) -> None:
        """Idle means 'nothing to do' and ends the peaceful turn immediately."""
        brain = _ScriptedBrain([Action(name=ActionType.IDLE), Action(name=ActionType.IDLE), END_TURN])
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain)

        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        actions = game_round.run_peaceful_turn(creature, world.time, query_fn, emit_fn)

        # First idle ends the turn — second idle and end_turn never reached
        assert len(actions) == 1
        assert actions[0].name == ActionType.IDLE

    def test_peaceful_turn_rejects_wait_for_stale_combat_member(self) -> None:
        """Regression (BLOCKER-peaceful-context-unpopulated): run_peaceful_turn is the
        supported legacy/internal dispatch path for a stale combat member
        (in_combat=False, still in active CombatState.turn_order). Its ActionContext
        must carry the authoritative combat_state so a non-rest PEACEFUL_ONLY action
        (WAIT here) is rejected by check_action_mode before the handler mutates
        anything — not just LONG_REST/SHORT_REST via their own defense-in-depth gate.
        """
        brain = _ScriptedBrain([Action(name=ActionType.WAIT, params={"hours": 1})])
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain, in_combat=False)
        foe = Creature(id="foe", name="Foe", location_id="r1", in_combat=False)

        world = _make_world([creature, foe])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        el._combat._combats["r1"] = CombatState(location_id="r1", turn_order=[creature.id, foe.id])
        game_round = Round(world, el)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        actions = game_round.run_peaceful_turn(creature, world.time, query_fn, emit_fn)

        # Rejected at validation — no action recorded, no mutation reached the handler.
        assert actions == []
        assert creature.current_intent is None
        assert creature.active is True

    def test_no_budget_in_peaceful(self) -> None:
        """Peaceful awareness has turn_budget=None."""
        received_budgets: list[TurnBudget | None] = []

        class BudgetCaptureBrain(Brain):
            def choose_action(
                self,
                creature: Creature,
                awareness: PeacefulAwareness | CombatAwareness,
                events: list[PerceivedEvent],
            ) -> Action:
                received_budgets.append(awareness.turn_budget)
                return END_TURN

        creature = Creature(id="c1", name="A", location_id="r1", brain=BudgetCaptureBrain())
        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        game_round.run_peaceful_turn(creature, world.time, query_fn, emit_fn)

        assert len(received_budgets) == 1
        assert received_budgets[0] is None

    def test_on_action_callback_gets_none_budget(self) -> None:
        """Peaceful on_action callback receives budget=None."""
        brain = _ScriptedBrain([Action(name=ActionType.SAY, params={"text": "hi"})])
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain)

        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        callback_log: list[tuple[str, str, TurnBudget | None]] = []

        def on_action(c: Creature, a: Action, b: TurnBudget | None, error: str = "") -> None:
            callback_log.append((c.id, a.name, b))

        game_round.set_on_action(on_action)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")
        game_round.run_peaceful_turn(creature, world.time, query_fn, emit_fn)

        assert len(callback_log) == 1
        assert callback_log[0] == ("c1", ActionType.SAY, None)

    def test_dispatcher_routes_by_combat_state(self) -> None:
        """run_creature_turn dispatches to combat or peaceful based on in_combat."""
        brain = _ScriptedBrain([END_TURN])
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain)

        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        query_fn = world.make_query_fn("entities")
        emit_fn = world.make_emit_fn("entities")

        # Peaceful
        creature.in_combat = False
        game_round.run_creature_turn(creature, world.time, query_fn, emit_fn)

        # Combat
        creature.in_combat = True
        brain._index = 0  # reset brain
        game_round.run_creature_turn(creature, world.time, query_fn, emit_fn)
