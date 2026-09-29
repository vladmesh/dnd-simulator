"""Two simultaneous combats and ``Round.stop()``: every combat runs each round exactly once.

Reported in sprint 1451: with combats in two locations, a stop gave the first combat an extra
round. A stop that falls in the second combat's turns interrupts the round after the first
combat has already finished its turns and closed its round (``end_combat_round``). The
interrupted round advances no time, so the next round replays the whole game round — and the
first combat, which has no resume cursor, ran a second full round at the same game time
(conditions ticked twice, a second ``round_number`` and idle-round increment).

The scenarios drive ``Round`` synchronously: a brain calls ``stop()`` from inside its decision,
which is exactly where a disconnect lands (the decision returning after it is discarded).
"""

from __future__ import annotations

from dnd_simulator.core.action import END_TURN, Action
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.location import Location, LocationEdge, LocationGraph
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.round import Round, RoundResult

_START = GameDateTime(year=1, month=1, day=1, hour=10)


class _Brain(Brain):
    """Ends every turn and logs it; optionally calls ``stop()`` inside chosen decisions.

    ``stop_on`` holds 1-based decision numbers of this brain at which the round is stopped,
    so the decision is discarded and the turn is interrupted mid-way.
    """

    def __init__(self, log: list[str], stop_on: tuple[int, ...] = ()) -> None:
        self._log = log
        self._stop_on = stop_on
        self.calls = 0
        self.round: Round | None = None

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        self.calls += 1
        if self.calls in self._stop_on:
            assert self.round is not None
            self.round.stop()
        else:
            self._log.append(creature.id)
        return END_TURN


def _world(entities: list[Creature]) -> World:
    region = Region(
        id="r1",
        name="Test Field",
        terrain=TerrainType.PLAINS,
        latitude=45.0,
        longitude=0.0,
        elevation=100,
        water_proximity=0.0,
        connections=[],
    )
    settlements = SettlementsLayer(settlements=[], region_terrains={"r1": TerrainType.PLAINS})
    politics = PoliticsLayer(
        nations=[],
        region_terrains={"r1": TerrainType.PLAINS},
        region_adjacency={},
        region_income_fn=settlements.get_region_income,
    )
    return World(
        layers=[GeographyLayer(regions=[region]), politics, settlements, EntitiesLayer(entities=list(entities))],
        time=_START,
        location_graph=LocationGraph(
            [
                Location("a", "Scene A", "r1", edges=(LocationEdge("b", 60_000),)),
                Location("b", "Scene B", "r1", edges=(LocationEdge("a", 60_000),)),
            ]
        ),
    )


def _entities(world: World) -> EntitiesLayer:
    return next(layer for layer in world.layers if isinstance(layer, EntitiesLayer))


class _Scenario:
    """Combat A (a1, a2) then combat B (b1, b2), in that iteration order, all brains logging to ``log``."""

    def __init__(self, *, a1_stop: tuple[int, ...] = (), b1_stop: tuple[int, ...] = ()) -> None:
        self.log: list[str] = []
        self.brains = {
            "a1": _Brain(self.log, a1_stop),
            "a2": _Brain(self.log),
            "b1": _Brain(self.log, b1_stop),
            "b2": _Brain(self.log),
        }
        creatures = [Creature(id=cid, name=cid, location_id=cid[0], brain=brain) for cid, brain in self.brains.items()]
        self.a1 = creatures[0]
        self.a1.conditions[Condition.POISONED] = 10
        self.world = _world(creatures)
        self.layer = _entities(self.world)
        self.combat_a = CombatState(location_id="a", turn_order=["a1", "a2"])
        self.combat_b = CombatState(location_id="b", turn_order=["b1", "b2"])
        self.layer._combat._combats["a"] = self.combat_a
        self.layer._combat._combats["b"] = self.combat_b

    def new_round(self) -> Round:
        game_round = Round(self.world, self.layer)
        for brain in self.brains.values():
            brain.round = game_round
        return game_round


class TestStopInSecondCombat:
    def test_first_combat_does_not_replay_its_finished_round(self) -> None:
        sc = _Scenario(b1_stop=(1,))
        first = sc.new_round().run_round()
        assert first.interrupted
        assert sc.log == ["a1", "a2"]
        assert sc.combat_a.round_number == 2
        assert sc.a1.conditions[Condition.POISONED] == 9
        assert sc.world.time == _START

        # Resume (reconnect): only combat B's remaining turns belong to this game round.
        resumed = sc.new_round().run_round()
        assert not resumed.interrupted
        assert sc.log == ["a1", "a2", "b1", "b2"]
        assert sc.combat_a.round_number == 2
        assert sc.combat_a.rounds_without_attack == 1
        assert sc.a1.conditions[Condition.POISONED] == 9
        assert sc.combat_b.round_number == 2
        assert sc.world.time.to_total_seconds() == _START.to_total_seconds() + 6

        # The next game round runs both combats again, each once (both then hit the idle
        # limit and end, so their creatures' peaceful turns follow).
        sc.new_round().run_round()
        assert sc.log[:8] == ["a1", "a2", "b1", "b2", "a1", "a2", "b1", "b2"]
        assert sc.a1.conditions[Condition.POISONED] == 8

    def test_stop_in_last_turn_of_second_combat(self) -> None:
        sc = _Scenario()
        sc.brains["b2"] = b2 = _Brain(sc.log, (1,))
        b2_creature = sc.layer.get_entity("b2")
        assert isinstance(b2_creature, Creature)
        b2_creature.brain = b2
        assert sc.new_round().run_round().interrupted
        sc.new_round().run_round()
        assert sc.log == ["a1", "a2", "b1", "b2"]
        assert sc.combat_a.round_number == 2
        assert sc.combat_b.round_number == 2

    def test_finished_round_marker_survives_save_load(self) -> None:
        sc = _Scenario(b1_stop=(1,))
        assert sc.new_round().run_round().interrupted
        state = sc.layer.get_state()

        restored_log: list[str] = []
        fresh = [Creature(id=cid, name=cid, location_id=cid[0]) for cid in ("a1", "a2", "b1", "b2")]
        restored_world = _world(fresh)
        restored_world.time = sc.world.time
        restored = _entities(restored_world)
        restored.load_state(state)
        for cid in ("a1", "a2", "b1", "b2"):
            creature = restored.get_entity(cid)
            assert isinstance(creature, Creature)
            creature.brain = _Brain(restored_log)

        Round(restored_world, restored).run_round()

        assert restored_log == ["b1", "b2"]
        combat_a = restored.get_combat("a")
        assert combat_a is not None
        assert combat_a.round_number == 2


class TestStopInFirstCombat:
    def test_resume_continues_first_combat_then_runs_second_once(self) -> None:
        sc = _Scenario(a1_stop=(1,))
        assert sc.new_round().run_round().interrupted
        assert sc.log == []
        assert sc.combat_b.round_number == 1

        sc.new_round().run_round()
        assert sc.log == ["a1", "a2", "b1", "b2"]
        assert sc.combat_a.round_number == 2
        assert sc.combat_b.round_number == 2
        # The interrupted, already started turn is continued, not re-ticked.
        assert sc.a1.conditions[Condition.POISONED] == 9


class TestStopBetweenRounds:
    def test_stop_after_a_completed_round_runs_the_next_round_normally(self) -> None:
        sc = _Scenario()
        game_round = sc.new_round()

        def on_round_end(_result: RoundResult) -> None:
            game_round.stop()

        game_round.set_on_round_end(on_round_end)
        game_round.run_loop()
        assert sc.log == ["a1", "a2", "b1", "b2"]
        assert sc.combat_a.resume_turn_index is None
        assert sc.combat_b.resume_turn_index is None

        sc.new_round().run_round()
        # Both combats hit the idle limit this round; their creatures' peaceful turns follow.
        assert sc.log[:8] == ["a1", "a2", "b1", "b2", "a1", "a2", "b1", "b2"]
        assert sc.combat_a.round_number == 3
        assert sc.combat_b.round_number == 3
        assert sc.a1.conditions[Condition.POISONED] == 8


class TestFirstCombatEndsWhileSecondIsInterrupted:
    def test_ended_combat_stays_ended_and_second_combat_resumes(self) -> None:
        sc = _Scenario(b1_stop=(2,))
        # Round 1 completes for both; in round 2 combat A reaches the idle limit and ends,
        # then combat B is interrupted.
        sc.new_round().run_round()
        assert sc.new_round().run_round().interrupted
        assert sc.layer.get_combat("a") is None
        assert sc.log == ["a1", "a2", "b1", "b2", "a1", "a2"]

        sc.new_round().run_round()
        # Combat A is over: its creatures now take peaceful turns after combat B's resumed turns.
        assert sc.log[6:8] == ["b1", "b2"]
        assert sc.layer.get_combat("a") is None
        assert sc.combat_b.round_number == 3
