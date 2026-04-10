"""Tests: creature killed mid-turn (e.g. by OA) produces no further actions."""

from __future__ import annotations

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.round import Round


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


class _DieAfterFirstActionBrain(Brain):
    """Brain that returns actions. Creature is killed externally after first action.

    Simulates a creature dying mid-turn from a reaction (e.g. opportunity attack)
    that resolves between brain calls.
    """

    def __init__(self) -> None:
        self._call_count = 0

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        self._call_count += 1
        if self._call_count == 1:
            return Action(name=ActionType.DODGE)
        # Should never reach here — loop should break on is_alive check
        raise AssertionError("Brain called after creature died — liveness check missing")


class TestDeadCreatureMidTurn:
    def test_creature_killed_mid_turn_no_further_actions(self) -> None:
        """After a creature dies mid-turn, the combat loop stops immediately.

        No further brain calls, no DEAD_ACTOR validation errors.
        """
        creature = Creature(
            id="c1",
            name="Goblin",
            location_id="r1",
            max_hp=10,
            current_hp=10,
            in_combat=True,
        )
        creature.brain = _DieAfterFirstActionBrain()

        # Need a second creature so combat context is valid
        target = Creature(id="c2", name="Hero", location_id="r1", max_hp=50, current_hp=50)

        world = _make_world([creature, target])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        query_fn = world._make_query_fn("entities")
        emit_fn = world._make_emit_fn("entities")

        # Kill the creature after first successful action (simulates OA death)
        def on_action(c: Creature, a: Action, b: TurnBudget | None, error: str = "") -> None:
            if error == "":
                c.current_hp = 0

        game_round.set_on_action(on_action)

        actions = game_round.run_combat_turn(creature, world.time, query_fn, emit_fn)

        # Only the first action (dodge) should have executed
        assert len(actions) == 1
        assert actions[0].name == ActionType.DODGE
        # Creature is dead
        assert not creature.is_alive

    def test_combat_round_skips_dead_creature_after_oa_kill(self) -> None:
        """In a full round, a creature killed by another creature's turn
        doesn't get its own turn.
        """
        # Creature that was already dead before its turn
        dead_creature = Creature(
            id="dead1",
            name="Dead Goblin",
            location_id="r1",
            max_hp=10,
            current_hp=0,  # already dead
            in_combat=True,
        )

        class NeverCalledBrain(Brain):
            def choose_action(
                self,
                creature: Creature,
                awareness: PeacefulAwareness | CombatAwareness,
                events: list[PerceivedEvent],
            ) -> Action:
                raise AssertionError("Brain should never be called for a dead creature")

        dead_creature.brain = NeverCalledBrain()

        alive_creature = Creature(
            id="alive1",
            name="Hero",
            location_id="r1",
            max_hp=50,
            current_hp=50,
            in_combat=True,
            brain=_ScriptedBrain([END_TURN]),
        )

        world = _make_world([dead_creature, alive_creature])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))
        game_round = Round(world, el)

        # run_round checks is_alive before starting a turn — this test
        # confirms the outer loop guard (line 539) still works
        game_round.run_round()
        # If we get here without AssertionError, the dead creature was skipped


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
