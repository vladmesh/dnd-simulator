"""Quick integration test: run arena combat and verify summarizer fires."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Project imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.llm.summarizer import MemorySummarizer

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

CONTENT_DIR = Path(__file__).resolve().parents[1] / "content"


def main() -> None:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat-v3-0324")
    if not api_key:
        print("ERROR: set OPENROUTER_API_KEY in .env")
        sys.exit(1)

    llm = LlmClient(api_key=api_key, model=model)
    summarizer = MemorySummarizer(llm)

    world_path = CONTENT_DIR / "worlds" / "arena.yaml"
    regions = load_world(world_path)
    nations = load_nations(world_path)
    settlements = load_settlements(world_path)
    player = load_player(world_path)
    npcs = load_npcs(world_path)
    battle_maps = load_battle_maps(world_path)
    locations = load_locations(world_path, regions)
    location_graph = LocationGraph(locations)

    if not player.location_id and locations:
        player.location_id = locations[0].id

    region_terrains = extract_region_terrains(regions)
    geography = GeographyLayer(regions=regions)
    settlements_layer = SettlementsLayer(settlements=settlements, region_terrains=region_terrains)
    politics = PoliticsLayer(
        nations=nations,
        region_terrains=region_terrains,
        region_adjacency=extract_region_adjacency(regions),
        region_income_fn=settlements_layer.get_region_income,
    )
    entities_layer = EntitiesLayer(
        entities=[*npcs, player],
        battle_map_configs=battle_maps,
        summarizer=summarizer,
    )

    world = World(
        layers=[geography, settlements_layer, politics, entities_layer],
        time=GameDateTime(year=1490, month=6, day=1, hour=10),
        location_graph=location_graph,
    )
    world.advance_time(TimeDelta(seconds=0))

    # Print NPC memories BEFORE combat
    print("\n=== NPC MEMORIES BEFORE COMBAT ===")
    for npc in npcs:
        print(f"  {npc.name}: tags={npc.memory.tags}, recent='{npc.memory.recent}'")

    # Player auto-attacks the first NPC to start combat
    from dnd_simulator.core.models import Event, EventType

    print("\n=== STARTING COMBAT ===")
    target_npc = npcs[0]
    world.handle_event(
        Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": player.id, "target_id": target_npc.id},
        )
    )
    print(f"Player attacks {target_npc.name}")

    # Run combat rounds — all NPCs use RuleBrain, player auto-attacks nearest alive enemy
    from dnd_simulator.core.character import Creature

    max_rounds = 30
    for round_num in range(1, max_rounds + 1):
        combat_locations = entities_layer.get_combat_locations()
        if not combat_locations:
            print(f"\n--- Combat ended after round {round_num - 1} ---")
            break

        for loc_id in list(combat_locations):
            combat = entities_layer.get_combat(loc_id)
            if not combat:
                continue

            for entity_id in list(combat.turn_order):
                entity = entities_layer.get_entity(entity_id)
                if not isinstance(entity, Creature) or not entity.is_alive or not entity.active:
                    continue

                if entity.id == player.id:
                    # Player auto-attacks nearest alive enemy
                    alive_enemies = [
                        e for e in entities_layer.get_active_creatures()
                        if e.id != player.id and e.is_alive and e.in_combat
                    ]
                    if alive_enemies:
                        target = alive_enemies[0]
                        world.handle_event(
                            Event(
                                event_type=EventType.ENTITY_ATTACK,
                                source_layer="entities",
                                data={"attacker_id": player.id, "target_id": target.id},
                            )
                        )
                else:
                    # NPC takes turn via brain
                    entity.is_dodging = False
                    entity.take_turn(world)

            entities_layer.end_combat_round(loc_id)

        # Brief status
        alive = [e for e in entities_layer.get_active_creatures() if e.is_alive]
        status = ", ".join(f"{e.name}({e.current_hp}hp)" for e in alive)
        print(f"  Round {round_num}: {status}")
    else:
        print(f"\n--- Max rounds ({max_rounds}) reached, forcing combat end ---")
        # Force end: 3 idle rounds (no attacks) to trigger COMBAT_ENDED
        for loc_id in list(entities_layer.get_combat_locations()):
            entities_layer.end_combat_round(loc_id)
            entities_layer.end_combat_round(loc_id)
            entities_layer.end_combat_round(loc_id)

    # Print NPC memories AFTER combat
    print("\n=== NPC MEMORIES AFTER COMBAT ===")
    for npc in npcs:
        print(f"  {npc.name} [alive={npc.is_alive}]:")
        print(f"    tags: {npc.memory.tags}")
        print(f"    recent: '{npc.memory.recent}'")
        print(f"    inner_state: '{npc.memory.inner_state}'")


if __name__ == "__main__":
    main()
