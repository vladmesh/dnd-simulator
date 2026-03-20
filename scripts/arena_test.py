#!/usr/bin/env python3
"""Run the Blood Arena for a few rounds with an auto-attacking player."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from dnd_simulator.content_loader import (
    load_battle_maps,
    load_nations,
    load_npcs,
    load_player,
    load_settlements,
    load_world,
)
from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import Event, EventType, GameDateTime, TimeDelta
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.llm.client import LlmClient

CONTENT_DIR = Path(__file__).resolve().parents[1] / "content"
MAX_ROUNDS = 4


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stderr)])
    load_dotenv()

    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("LLM_MODEL")
    if not api_key or not model:
        print("Error: set OPENROUTER_API_KEY and LLM_MODEL in .env")
        sys.exit(1)
    llm = LlmClient(api_key=api_key, model=model)
    print(f"LLM: {model}\n")

    world_path = CONTENT_DIR / "worlds" / "arena.yaml"
    regions = load_world(world_path)
    nations = load_nations(world_path)
    settlements = load_settlements(world_path)
    player = load_player(world_path)
    npcs = load_npcs(world_path)
    battle_maps = load_battle_maps(world_path)

    for npc in npcs:
        npc.llm = llm

    # Player auto-attacks nearest enemy (no human input needed)
    def auto_input(prompt: str) -> str:
        """Auto-play: attack nearest living enemy."""
        combat = entities_layer.get_combat("arena")
        if not combat:
            return "idle"
        my_pos = combat.battle_map.get_position("player")
        if my_pos is None:
            return "idle"

        from dnd_simulator.rules.movement import grid_distance

        best_id = ""
        best_dist = 999999
        for eid, pos in combat.battle_map.positions.items():
            if eid == "player":
                continue
            e = entities_layer.get_entity(eid)
            if isinstance(e, Creature) and e.is_alive:
                d = grid_distance(my_pos, pos)
                if d < best_dist:
                    best_dist = d
                    best_id = eid

        if not best_id:
            return "idle"

        # If in melee range, attack; otherwise move toward
        if best_dist <= 5:
            return f"attack {best_id}"
        return f"move toward {best_id}"

    player.input_fn = auto_input
    player.output_fn = print

    geography = GeographyLayer(regions=regions)
    settlements_layer = SettlementsLayer(settlements=settlements, region_terrains={r.id: r.terrain.value for r in regions})
    politics = PoliticsLayer(
        nations=nations,
        region_terrains={r.id: r.terrain.value for r in regions},
        region_adjacency={r.id: [c.target_id for c in r.connections] for r in regions},
        region_income_fn=settlements_layer.get_region_income,
    )
    entities_layer = EntitiesLayer(entities=[*npcs, player], battle_map_configs=battle_maps)

    world = World(
        layers=[geography, settlements_layer, politics, entities_layer],
        time=GameDateTime(year=1490, month=6, day=1, hour=12),
    )
    world.advance_time(TimeDelta(seconds=0))

    print("=== КРОВАВАЯ АРЕНА ===\n")
    print("Бойцы:")
    for npc in npcs:
        print(f"  {npc.name} — HP:{npc.max_hp} AC:{npc.ac} [{npc.attacks[0].name}]")
    print(f"  {player.name} (игрок) — HP:{player.max_hp} AC:{player.ac} [{player.attacks[0].name}]")
    print()

    # Player attacks first to trigger combat
    print("--- Игрок начинает бой! ---\n")
    first_target = npcs[0].id
    world.handle_event(
        Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "player", "target_id": first_target},
        )
    )

    # Show initial positions and walls
    combat = entities_layer.get_combat("arena")
    if combat:
        walls_desc = combat.battle_map.describe_walls()
        if walls_desc:
            print("Стены:")
            for w in walls_desc:
                print(f"  {w}")
            print()
        print("Стартовые позиции:")
        for eid, pos in combat.battle_map.positions.items():
            e = entities_layer.get_entity(eid)
            name = e.name if e else eid
            print(f"  {name}: ({pos.x}, {pos.y})")
        print()

    # Run combat rounds
    for round_num in range(1, MAX_ROUNDS + 1):
        combat = entities_layer.get_combat("arena")
        if not combat:
            print("=== Бой окончен ===")
            break

        print(f"{'='*50}")
        print(f"РАУНД {combat.round_number}")
        print(f"{'='*50}")

        for entity_id in list(combat.turn_order):
            entity = entities_layer.get_entity(entity_id)
            if not isinstance(entity, Creature) or not entity.is_alive or not entity.active or not entity.in_combat:
                continue

            entity.is_dodging = False
            pos = combat.battle_map.get_position(entity_id)
            pos_str = f"({pos.x},{pos.y})" if pos else "?"
            print(f"\n  [{entity.name}] HP:{entity.current_hp}/{entity.max_hp} pos:{pos_str}")
            entity.take_turn(world)

            # Show what happened
            if isinstance(entity, Creature):
                new_pos = combat.battle_map.get_position(entity_id) if combat else None
                if new_pos and new_pos != pos:
                    print(f"    → переместился в ({new_pos.x},{new_pos.y})")

        entities_layer.end_combat_round("arena")
        world.advance_time(TimeDelta.from_rounds(1))

        # Status after round
        print(f"\n--- Статус после раунда {round_num} ---")
        alive_count = 0
        for e in [*npcs, player]:
            status = f"HP:{e.current_hp}/{e.max_hp}" if e.is_alive else "МЁРТВ"
            print(f"  {e.name}: {status}")
            if e.is_alive:
                alive_count += 1
        print()

        if alive_count <= 1:
            print("=== ПОБЕДИТЕЛЬ ОПРЕДЕЛЁН ===")
            for e in [*npcs, player]:
                if e.is_alive:
                    print(f"  🏆 {e.name} побеждает!")
            break

    # Final event log
    print("\n--- Лог боя (глазами игрока) ---")
    log = entities_layer.get_perceived_log(player)
    for line in log:
        print(f"  {line}")


if __name__ == "__main__":
    main()
