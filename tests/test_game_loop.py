"""Tests for time advancement in the game loop and player wait command."""

from __future__ import annotations

from dataclasses import dataclass

from dnd_simulator.core.character import Creature
from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.game_loop import run_game_loop
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer


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
        layers=[geography, settlements, politics, entities_layer],
        time=GameDateTime(year=1, month=1, day=1, hour=hour),
        location_graph=LocationGraph([Location(id="r1", name="Test Field", region_id="r1")]),
    )


@dataclass
class _OneShotCreature(Creature):
    """Creature that deactivates itself after one turn."""

    def take_turn(self, world: World) -> None:
        self.active = False


class TestGameLoopTimeAdvancement:
    def test_time_advances_by_one_round_per_loop_iteration(self) -> None:
        """After all creatures act, world time advances by 6 seconds."""
        npc = _OneShotCreature(id="npc1", name="Guard", location_id="r1")
        world = _make_world([npc])

        initial_seconds = world.time.to_total_seconds()
        run_game_loop(world)

        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 6  # 1 round = 6 seconds

    def test_multiple_creatures_still_one_round(self) -> None:
        """Multiple creatures acting in one round = still only 6 seconds."""
        c1 = _OneShotCreature(id="c1", name="A", location_id="r1")
        c2 = _OneShotCreature(id="c2", name="B", location_id="r1")
        world = _make_world([c1, c2])

        initial_seconds = world.time.to_total_seconds()
        run_game_loop(world)

        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 6


class TestPlayerWaitCommand:
    def test_wait_default_one_hour(self) -> None:
        """'wait' without argument advances time by 1 hour."""
        output: list[str] = []
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            input_fn=lambda _: "wait",
            output_fn=output.append,
        )
        world = _make_world([player], hour=10)

        initial_seconds = world.time.to_total_seconds()
        player.take_turn(world)

        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 3600  # 1 hour
        assert any("1 h" in s for s in output)

    def test_wait_custom_hours(self) -> None:
        """'wait 3' advances time by 3 hours."""
        output: list[str] = []
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            input_fn=lambda _: "wait 3",
            output_fn=output.append,
        )
        world = _make_world([player], hour=10)

        initial_seconds = world.time.to_total_seconds()
        player.take_turn(world)

        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 3 * 3600
        assert any("3 h" in s for s in output)

    def test_wait_invalid_argument(self) -> None:
        """'wait abc' shows error and doesn't end turn."""
        output: list[str] = []
        inputs = iter(["wait abc", "idle"])
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            input_fn=lambda _: next(inputs),
            output_fn=output.append,
        )
        world = _make_world([player], hour=10)

        initial_seconds = world.time.to_total_seconds()
        player.take_turn(world)

        elapsed = world.time.to_total_seconds() - initial_seconds
        assert elapsed == 0

    def test_wait_zero_hours_rejected(self) -> None:
        """'wait 0' shows error."""
        output: list[str] = []
        inputs = iter(["wait 0", "idle"])
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            input_fn=lambda _: next(inputs),
            output_fn=output.append,
        )
        world = _make_world([player], hour=10)

        player.take_turn(world)
        assert any("Minimum" in s for s in output)
