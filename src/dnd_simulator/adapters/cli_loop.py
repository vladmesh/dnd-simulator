"""CLI adapter using the new turn-based game loop."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from dnd_simulator.content_loader import (
    extract_region_adjacency,
    extract_region_terrains,
    load_nations,
    load_npcs,
    load_player,
    load_settlements,
    load_world,
)
from dnd_simulator.core.models import GameDateTime, TimeDelta
from dnd_simulator.core.world import World
from dnd_simulator.game_loop import run_game_loop
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.llm.client import LlmClient

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"


def _quit_input(prompt: str) -> str:
    """Wrapper around input() that handles quit/EOF."""
    try:
        text = input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\nПрощай, искатель приключений.")
        sys.exit(0)
    if text.strip().lower() == "quit":
        print("Прощай, искатель приключений.")
        sys.exit(0)
    return text


def run_cli_loop() -> None:
    """Start the game using the turn-based loop."""
    load_dotenv()

    # LLM setup
    llm: LlmClient | None = None
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if api_key:
        model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat-v3-0324")
        llm = LlmClient(api_key=api_key, model=model)
        print(f"LLM: {model}")
    else:
        print("LLM: not configured (set OPENROUTER_API_KEY in .env)")

    # Load world
    world_path = DEFAULT_CONTENT_DIR / "worlds" / "test_world.yaml"
    regions = load_world(world_path)
    nations = load_nations(world_path)
    settlements = load_settlements(world_path)
    player = load_player(world_path)
    npcs = load_npcs(world_path)

    # Inject LLM into NPCs
    if llm:
        for npc in npcs:
            npc.llm = llm

    # Fall back to first region if player has no start_region
    if not player.region_id and regions:
        player.region_id = regions[0].id

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
    entities_layer = EntitiesLayer(entities=[*npcs, player])

    world = World(
        layers=[geography, settlements_layer, politics, entities_layer],
        time=GameDateTime(year=1490, month=6, day=1, hour=10),
    )

    # Initial tick
    world.advance_time(TimeDelta(seconds=0))

    print("=== D&D Simulator (Turn-Based) ===")
    print("Команды: look, status, say <текст>, attack <цель> [оружие], idle, quit\n")

    run_game_loop(world)


if __name__ == "__main__":
    run_cli_loop()
