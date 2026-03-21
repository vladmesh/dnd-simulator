"""Tests for multi-action turn loop, TurnBudget, and action cost enforcement."""

from __future__ import annotations

from dnd_simulator.core.action import END_TURN, Action
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Ability, Attack, Creature, DamageComponent, DamageType
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
        cost = action_cost(Action(name="attack", params={"target_id": "x"}))
        assert cost.actions == 1
        assert cost.bonus_actions == 0

    def test_idle_is_free(self) -> None:
        cost = action_cost(Action(name="idle"))
        assert cost.actions == 0 and cost.bonus_actions == 0 and cost.movement_ft == 0

    def test_end_turn_is_free(self) -> None:
        cost = action_cost(END_TURN)
        assert cost.actions == 0

    def test_say_is_free(self) -> None:
        cost = action_cost(Action(name="say", params={"text": "hi"}))
        assert cost.actions == 0

    def test_dodge_costs_one_action(self) -> None:
        cost = action_cost(Action(name="dodge"))
        assert cost.actions == 1

    def test_move_costs_movement(self) -> None:
        cost = action_cost(Action(name="move", params={"toward": "x"}))
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
        brain = _ScriptedBrain([Action(name="say", params={"text": "hi"}), END_TURN])
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain)
        creature.active = False  # prevent loop from repeating

        world = _make_world([creature])
        creature.active = True
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        query_fn = world._make_query_fn("entities")
        emit_fn = world._make_emit_fn("entities")
        actions = game_round.run_creature_turn(creature, world.time, query_fn, emit_fn)

        assert len(actions) == 1
        assert actions[0].name == "say"

    def test_budget_exhaustion_ends_turn(self) -> None:
        """When budget runs out, turn ends even without end_turn."""
        sword = Attack(
            name="sword",
            ability=Ability.STR,
            damage=(DamageComponent(dice="1d8", type=DamageType.SLASHING),),
            reach=5,
        )
        # Brain tries to attack twice, but only has 1 action
        brain = _ScriptedBrain(
            [
                Action(name="attack", params={"target_id": "target1"}),
                Action(name="attack", params={"target_id": "target1"}),
            ]
        )
        attacker = Creature(
            id="c1",
            name="A",
            location_id="r1",
            brain=brain,
            max_hp=20,
            current_hp=20,
            attacks=(sword,),
        )
        target = Creature(id="target1", name="T", location_id="r1", max_hp=100, current_hp=100)

        world = _make_world([attacker, target])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        query_fn = world._make_query_fn("entities")
        emit_fn = world._make_emit_fn("entities")
        actions = game_round.run_creature_turn(attacker, world.time, query_fn, emit_fn)

        # Only 1 attack should have executed (budget has 1 action)
        assert len(actions) == 1
        assert actions[0].name == "attack"

    def test_free_action_then_costly_action(self) -> None:
        """Free action (say) + costly action (dodge) both execute."""
        brain = _ScriptedBrain(
            [
                Action(name="say", params={"text": "prepare!"}),
                Action(name="dodge"),
                END_TURN,
            ]
        )
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain)

        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        query_fn = world._make_query_fn("entities")
        emit_fn = world._make_emit_fn("entities")
        actions = game_round.run_creature_turn(creature, world.time, query_fn, emit_fn)

        assert len(actions) == 2
        assert actions[0].name == "say"
        assert actions[1].name == "dodge"

    def test_on_action_callback_fires(self) -> None:
        """on_action callback fires after each action with current budget."""
        brain = _ScriptedBrain([Action(name="say", params={"text": "hi"}), END_TURN])
        creature = Creature(id="c1", name="A", location_id="r1", brain=brain)

        world = _make_world([creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        callback_log: list[tuple[str, str, int]] = []

        def on_action(c: Creature, a: Action, b: TurnBudget) -> None:
            callback_log.append((c.id, a.name, b.actions))

        game_round.set_on_action(on_action)

        query_fn = world._make_query_fn("entities")
        emit_fn = world._make_emit_fn("entities")
        game_round.run_creature_turn(creature, world.time, query_fn, emit_fn)

        assert len(callback_log) == 1
        assert callback_log[0] == ("c1", "say", 1)  # say is free, actions still 1

    def test_awareness_includes_budget(self) -> None:
        """The awareness passed to choose_action includes turn_budget."""
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

        query_fn = world._make_query_fn("entities")
        emit_fn = world._make_emit_fn("entities")
        game_round.run_creature_turn(creature, world.time, query_fn, emit_fn)

        assert len(received_budgets) == 1
        budget = received_budgets[0]
        assert budget is not None
        assert budget.actions == 1
        assert budget.bonus_actions == 1
        assert budget.movement_remaining == creature.speed
