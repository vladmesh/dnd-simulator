"""Tests for multi-action turn loop, TurnBudget, and action cost enforcement."""

from __future__ import annotations

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import GameDateTime
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

    def test_move_costs_movement(self) -> None:
        cost = action_cost(Action(name=ActionType.MOVE, params={"toward": "x"}))
        assert cost.movement_ft == 5


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
