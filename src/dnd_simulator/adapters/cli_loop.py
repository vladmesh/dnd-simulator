"""CLI adapter using the new turn-based game loop."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from dnd_simulator.content_loader import (
    extract_region_adjacency,
    extract_region_terrains,
    load_battle_maps,
    load_locations,
    load_nations,
    load_npcs,
    load_player,
    load_settlements,
    load_world,
)
from dnd_simulator.core.location import LocationGraph
from dnd_simulator.core.models import GameDateTime, TimeDelta
from dnd_simulator.core.world import World
from dnd_simulator.game_loop import run_game_loop
from dnd_simulator.i18n import _
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.llm.brain import LlmBrain
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.llm.summarizer import MemorySummarizer

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"


def _quit_input(prompt: str) -> str:
    """Wrapper around input() that handles quit/EOF."""
    try:
        text = input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\n" + _("Farewell, adventurer."))
        sys.exit(0)
    if text.strip().lower() == "quit":
        print(_("Farewell, adventurer."))
        sys.exit(0)
    return text


def run_cli_loop() -> None:
    """Start the game using the turn-based loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    load_dotenv()

    # LLM setup
    llm: LlmClient | None = None
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("LLM_MODEL")
    if not api_key or not model:
        print(_("Error: set OPENROUTER_API_KEY and LLM_MODEL in .env"))
        sys.exit(1)
    llm = LlmClient(api_key=api_key, model=model)
    print(f"LLM: {model}")

    # Load world (accept filename from argv)
    world_file = sys.argv[1] if len(sys.argv) > 1 else "test_world.yaml"
    world_path = DEFAULT_CONTENT_DIR / "worlds" / world_file
    regions = load_world(world_path)
    nations = load_nations(world_path)
    settlements = load_settlements(world_path)
    player = load_player(world_path)
    npcs = load_npcs(world_path)
    battle_maps = load_battle_maps(world_path)

    # Inject LLM brain into NPCs that need it
    for npc in npcs:
        if npc.ai_type == "llm":
            npc.brain = LlmBrain(llm)

    # Build location graph
    locations = load_locations(world_path, regions)
    location_graph = LocationGraph(locations)

    # Fall back to first location
    if not player.location_id and locations:
        player.location_id = locations[0].id

    # Player I/O
    player.input_fn = _quit_input
    player.output_fn = print

    # Build layers
    region_terrains = extract_region_terrains(regions)
    geography = GeographyLayer(regions=regions)
    settlements_layer = SettlementsLayer(settlements=settlements, region_terrains=region_terrains)
    politics = PoliticsLayer(
        nations=nations,
        region_terrains=region_terrains,
        region_adjacency=extract_region_adjacency(regions),
        region_income_fn=settlements_layer.get_region_income,
    )
    summarizer = MemorySummarizer(llm) if llm else None
    entities_layer = EntitiesLayer(entities=[*npcs, player], battle_map_configs=battle_maps, summarizer=summarizer)

    world = World(
        layers=[geography, settlements_layer, politics, entities_layer],
        time=GameDateTime(year=1490, month=6, day=1, hour=10),
        location_graph=location_graph,
    )

    # Initial tick
    world.advance_time(TimeDelta(seconds=0))

    print(_("=== D&D Simulator (Turn-Based) ==="))
    print(_("Commands: look, status, say <text>, attack <target>, idle, quit"))

    run_game_loop(world)


if __name__ == "__main__":
    run_cli_loop()
