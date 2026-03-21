"""Test canned dialogue: player talks to NPCs in a village, they respond."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dnd_simulator.content_loader import (
    extract_region_adjacency,
    extract_region_terrains,
    load_locations,
    load_nations,
    load_npcs,
    load_player,
    load_settlements,
    load_world,
)
from dnd_simulator.core.character import Creature
from dnd_simulator.core.location import LocationGraph
from dnd_simulator.core.models import Event, EventType, GameDateTime, TimeDelta
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer

CONTENT_DIR = Path(__file__).resolve().parents[1] / "content"


def main() -> None:
    world_path = CONTENT_DIR / "worlds" / "village.yaml"
    regions = load_world(world_path)
    nations = load_nations(world_path)
    settlements = load_settlements(world_path)
    player = load_player(world_path)
    npcs = load_npcs(world_path)
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
    entities_layer = EntitiesLayer(entities=[*npcs, player])

    world = World(
        layers=[geography, settlements_layer, politics, entities_layer],
        time=GameDateTime(year=1490, month=6, day=1, hour=12),
        location_graph=location_graph,
    )
    world.advance_time(TimeDelta(seconds=0))

    # NOTE: content_loader resolves NPC start_location from schedule, so NPCs
    # get location_id like "millbrook_home". For canned dialogue to work,
    # player and NPCs must share the same location_id.
    # Put everyone at the NPC default location.
    LOC = npcs[0].location_id  # "millbrook_home"
    player.location_id = LOC
    for npc in npcs:
        npc.location_id = LOC

    def say_and_tick(text: str, target_npcs: list[Npc] | None = None) -> None:
        """Player says something, then specified NPCs get a turn to respond."""
        print(f'\nСтранник: "{text}"')
        world.handle_event(
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data={"entity_id": player.id, "text": text},
            )
        )
        targets = target_npcs or npcs
        log_before = len(entities_layer._location_log.get(LOC, []))
        for npc in targets:
            if npc.active and not npc.in_combat:
                npc.take_turn(world)

        # Show new events since before NPC turns
        log = entities_layer._location_log.get(LOC, [])
        for evt in log[log_before:]:
            if evt.event_type == EventType.ENTITY_SAY:
                speaker_id = evt.data["entity_id"]
                speaker = entities_layer.get_entity(str(speaker_id))
                name = speaker.name if speaker else speaker_id
                print(f'  {name}: "{evt.data["text"]}"')

    # Show NPC info
    print("=== Тихая Деревня, полдень ===")
    for npc in npcs:
        act = npc.scheduled_activity(12)
        tags = npc.memory.tags
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        print(f"  {npc.name} ({npc.role}) — {act.value}{tag_str}")

    npc_by_id = {n.id: n for n in npcs}

    # Talk to merchant (working at noon)
    print("\n--- На рынке ---")
    say_and_tick("Здравствуйте! Что продаёте?", [npc_by_id["masha"]])

    # Talk to blacksmith (working at noon)
    print("\n--- В кузне ---")
    say_and_tick("Есть что-нибудь для меня?", [npc_by_id["olga"]])

    # Talk to farmer (working + grieving tag → mood override)
    print("\n--- На полях ---")
    say_and_tick("Добрый день, дедушка!", [npc_by_id["ivan"]])

    # Talk to guard (working at noon)
    print("\n--- На патруле ---")
    say_and_tick("Что нового?", [npc_by_id["sergei"]])

    # Talk to tavern keeper (working at noon)
    print("\n--- В таверне ---")
    say_and_tick("Что сегодня подают?", [npc_by_id["tanya"]])

    # Evening — blacksmith idle at tavern
    print("\n--- Вечер (20:00) ---")
    world.advance_time(TimeDelta.from_hours(8))  # noon → 20:00
    say_and_tick("Эй, кузнец! Как делишки?", [npc_by_id["olga"]])


if __name__ == "__main__":
    main()
