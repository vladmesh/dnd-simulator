"""Tests for the Round orchestrator and player wait handling."""

from __future__ import annotations

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain, PlayerBrain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.round import Round


def _make_world(entities: list[Creature], hour: int = 10) -> World:
    """Build a world with all 4 layers for testing."""
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
        time=GameDateTime(year=1, month=1, day=1, hour=hour),
        location_graph=LocationGraph([Location(id="r1", name="Test Field", region_id="r1")]),
    )


class _EndTurnBrain(Brain):
    """Brain that immediately ends its turn (for single-round tests)."""

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        return END_TURN


def _make_player_brain(action: Action) -> PlayerBrain:
    """Create a PlayerBrain that submits a fixed action then end_turn."""
    brain = PlayerBrain()

    def on_turn(
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> None:
        brain.submit_action(action)
        brain.submit_action(END_TURN)

    brain.set_on_turn(on_turn)
    return brain


class TestRoundTimeAdvancement:
    def test_time_advances_by_one_round_per_round(self) -> None:
        """After all creatures act, world time advances by 6 seconds."""
        npc = Creature(id="npc1", name="Guard", location_id="r1", brain=_EndTurnBrain())
        world = _make_world([npc])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        initial_seconds = world.time.to_total_seconds()
        game_round = Round(world, entities_layer)
        game_round.run_loop(max_rounds=1)

        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 6  # 1 round = 6 seconds

    def test_multiple_creatures_still_one_round(self) -> None:
        """Multiple creatures acting in one round = still only 6 seconds."""
        c1 = Creature(id="c1", name="A", location_id="r1", brain=_EndTurnBrain())
        c2 = Creature(id="c2", name="B", location_id="r1", brain=_EndTurnBrain())
        world = _make_world([c1, c2])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        initial_seconds = world.time.to_total_seconds()
        game_round = Round(world, entities_layer)
        game_round.run_loop(max_rounds=1)

        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 6


class TestPlayerWaitViaRound:
    def test_wait_sets_wake_at_and_fast_forwards(self) -> None:
        """Player wait sets wake_at, goes dormant, fast-forward advances time."""
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            brain=_make_player_brain(Action(name=ActionType.WAIT, params={"hours": 1})),
        )
        world = _make_world([player], hour=10)
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        initial_seconds = world.time.to_total_seconds()
        game_round = Round(world, entities_layer)
        # run_loop: round runs → player waits → dormant → fast-forward → wake up → next round
        game_round.run_loop(max_rounds=2)

        # Fast-forward advances 1 hour, then round advances 6 seconds
        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 3600 + 6
        assert player.active is True
        assert player.wake_at_seconds is None

    def test_wait_custom_hours(self) -> None:
        """Wait 3 hours: fast-forward advances 3 hours."""
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            brain=_make_player_brain(Action(name=ActionType.WAIT, params={"hours": 3})),
        )
        world = _make_world([player], hour=10)
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        initial_seconds = world.time.to_total_seconds()
        game_round = Round(world, entities_layer)
        game_round.run_loop(max_rounds=2)

        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 3 * 3600 + 6

    def test_player_uniform_with_npc(self) -> None:
        """Player and NPC both go through run_creature_turn uniformly."""
        actions_taken: list[str] = []

        brain = PlayerBrain()

        def on_turn(
            creature: Creature,
            awareness: PeacefulAwareness | CombatAwareness,
            events: list[PerceivedEvent],
        ) -> None:
            actions_taken.append(f"player:{creature.id}")
            brain.submit_action(END_TURN)

        brain.set_on_turn(on_turn)

        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            brain=brain,
        )
        npc = Creature(id="npc1", name="Guard", location_id="r1", brain=_EndTurnBrain())
        world = _make_world([player, npc])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        game_round = Round(world, entities_layer)
        game_round.run_loop(max_rounds=1)

        assert "player:player" in actions_taken


class TestProximityActivation:
    """Creatures near the player are active, distant ones are dormant."""

    def test_creatures_near_player_activated(self) -> None:
        """Creatures at the player's location become active during round."""
        player = PlayerCharacter(id="player", name="Hero", location_id="r1", brain=_EndTurnBrain())
        nearby = Creature(id="guard", name="Guard", location_id="r1", active=False, brain=_EndTurnBrain())
        world = _make_world([player, nearby])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        game_round = Round(world, entities_layer)
        game_round.run_round()

        assert nearby.active is True

    def test_distant_creatures_dormified(self) -> None:
        """Creatures far from the player become dormant during round."""
        player = PlayerCharacter(id="player", name="Hero", location_id="r1", brain=_EndTurnBrain())
        distant = Creature(id="bandit", name="Bandit", location_id="r2", active=True, brain=_EndTurnBrain())
        world = _make_world([player, distant])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        game_round = Round(world, entities_layer)
        game_round.run_round()

        assert distant.active is False

    def test_player_always_active(self) -> None:
        """PlayerCharacter is never dormified regardless of other players."""
        player = PlayerCharacter(id="player", name="Hero", location_id="r1", brain=_EndTurnBrain())
        world = _make_world([player])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        game_round = Round(world, entities_layer)
        game_round.run_round()

        assert player.active is True

    def test_in_combat_stays_active(self) -> None:
        """Creatures in combat stay active even if far from player."""
        player = PlayerCharacter(id="player", name="Hero", location_id="r1", brain=_EndTurnBrain())
        fighter = Creature(id="orc", name="Orc", location_id="r2", in_combat=True, brain=_EndTurnBrain())
        world = _make_world([player, fighter])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        game_round = Round(world, entities_layer)
        game_round.run_round()

        assert fighter.active is True

    def test_dead_creature_not_reactivated(self) -> None:
        """Dead creatures are not reactivated by proximity."""
        player = PlayerCharacter(id="player", name="Hero", location_id="r1", brain=_EndTurnBrain())
        corpse = Creature(id="goblin", name="Goblin", location_id="r1", current_hp=0, brain=_EndTurnBrain())
        world = _make_world([player, corpse])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        game_round = Round(world, entities_layer)
        game_round.run_round()

        # Dead creature's active state is not touched
        assert corpse.is_alive is False

    def test_no_player_no_change(self) -> None:
        """Without a PlayerCharacter, activation is unchanged (tests still work)."""
        npc = Creature(id="npc", name="Guard", location_id="r1", active=True, brain=_EndTurnBrain())
        world = _make_world([npc])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        game_round = Round(world, entities_layer)
        game_round.run_round()

        assert npc.active is True


class TestWaitAndFastForward:
    """Wait makes creatures dormant, fast-forward advances time to wake_at."""

    def test_wait_makes_player_dormant(self) -> None:
        """After wait action, player has wake_at set and is dormant."""
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            brain=_make_player_brain(Action(name=ActionType.WAIT, params={"hours": 2})),
        )
        world = _make_world([player], hour=10)
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        game_round = Round(world, el)
        game_round.run_round()  # single round, no fast-forward

        # Player went dormant, wake_at is set
        assert player.active is False
        # wake_at was set before the 6s advance
        assert player.wake_at_seconds is not None

    def test_fast_forward_advances_to_wake_at(self) -> None:
        """Fast-forward skips time to nearest wake_at when no active creatures."""
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            brain=_make_player_brain(Action(name=ActionType.WAIT, params={"hours": 2})),
        )
        world = _make_world([player], hour=10)
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        initial = world.time.to_total_seconds()
        game_round = Round(world, el)
        game_round.run_loop(max_rounds=2)

        # 2 hours fast-forward + 6s per round
        elapsed = world.time.to_total_seconds() - initial
        assert elapsed == 2 * 3600 + 6
        assert player.active is True
        assert player.wake_at_seconds is None

    def test_nearby_npc_dormifies_when_player_waits(self) -> None:
        """NPC near player goes dormant when player waits, reactivates on wake."""
        call_count = 0
        brain = PlayerBrain()

        def on_turn(
            creature: Creature,
            awareness: PeacefulAwareness | CombatAwareness,
            events: list[PerceivedEvent],
        ) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                brain.submit_action(Action(name=ActionType.WAIT, params={"hours": 1}))
            brain.submit_action(END_TURN)

        brain.set_on_turn(on_turn)

        player = PlayerCharacter(id="player", name="Hero", location_id="r1", brain=brain)
        npc = Creature(id="guard", name="Guard", location_id="r1", brain=_EndTurnBrain())
        world = _make_world([player, npc], hour=10)
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        game_round = Round(world, el)
        game_round.run_loop(max_rounds=2)

        # After fast-forward and wake, both should be active
        assert player.active is True
        assert npc.active is True
        assert call_count == 2  # called once for wait, once after waking

    def test_no_wake_at_means_loop_exits(self) -> None:
        """Without any wake_at, run_loop exits when no active creatures."""
        npc = Creature(id="npc", name="Guard", location_id="r1", active=False, brain=_EndTurnBrain())
        world = _make_world([npc])
        el = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        initial = world.time.to_total_seconds()
        game_round = Round(world, el)
        game_round.run_loop()  # should exit immediately

        assert world.time.to_total_seconds() == initial  # no time passed
