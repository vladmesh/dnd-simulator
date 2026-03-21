"""Tests for the Round orchestrator and player wait handling."""

from __future__ import annotations

from dnd_simulator.core.action import END_TURN, Action
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


class _DeactivateBrain(Brain):
    """Brain that deactivates the creature after one turn (for test loop termination)."""

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        creature.active = False
        return END_TURN


def _make_player_brain(action: Action) -> PlayerBrain:
    """Create a PlayerBrain that submits a fixed action then end_turn, then deactivates."""
    brain = PlayerBrain()

    def on_turn(
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> None:
        creature.active = False
        brain.submit_action(action)
        brain.submit_action(END_TURN)

    brain.set_on_turn(on_turn)
    return brain


class TestRoundTimeAdvancement:
    def test_time_advances_by_one_round_per_round(self) -> None:
        """After all creatures act, world time advances by 6 seconds."""
        npc = Creature(id="npc1", name="Guard", location_id="r1", brain=_DeactivateBrain())
        world = _make_world([npc])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        initial_seconds = world.time.to_total_seconds()
        game_round = Round(world, entities_layer)
        game_round.run_loop()

        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 6  # 1 round = 6 seconds

    def test_multiple_creatures_still_one_round(self) -> None:
        """Multiple creatures acting in one round = still only 6 seconds."""
        c1 = Creature(id="c1", name="A", location_id="r1", brain=_DeactivateBrain())
        c2 = Creature(id="c2", name="B", location_id="r1", brain=_DeactivateBrain())
        world = _make_world([c1, c2])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        initial_seconds = world.time.to_total_seconds()
        game_round = Round(world, entities_layer)
        game_round.run_loop()

        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 6


class TestPlayerWaitViaRound:
    def test_wait_default_one_hour(self) -> None:
        """Player brain returns wait action → Round advances time by 1 hour."""
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            brain=_make_player_brain(Action(name="wait", params={"hours": 1})),
        )
        world = _make_world([player], hour=10)
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        initial_seconds = world.time.to_total_seconds()
        game_round = Round(world, entities_layer)
        game_round.run_round()

        # Wait adds 1 hour + 1 round (6 seconds)
        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 3600 + 6

    def test_wait_custom_hours(self) -> None:
        """Wait 3 hours advances time by 3 hours."""
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            brain=_make_player_brain(Action(name="wait", params={"hours": 3})),
        )
        world = _make_world([player], hour=10)
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        initial_seconds = world.time.to_total_seconds()
        game_round = Round(world, entities_layer)
        game_round.run_round()

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
            creature.active = False
            brain.submit_action(END_TURN)

        brain.set_on_turn(on_turn)

        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            brain=brain,
        )
        npc = Creature(id="npc1", name="Guard", location_id="r1", brain=_DeactivateBrain())
        world = _make_world([player, npc])
        entities_layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        game_round = Round(world, entities_layer)
        game_round.run_loop()

        assert "player:player" in actions_taken
