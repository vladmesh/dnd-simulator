"""Main game loop — polls all active creatures in turn order."""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import TimeDelta
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer


def get_entities_layer(world: World) -> EntitiesLayer:
    """Find the entities layer in the world."""
    for layer in world.layers:
        if isinstance(layer, EntitiesLayer):
            return layer
    raise RuntimeError("World has no EntitiesLayer")


def run_game_loop(world: World) -> None:
    """Run the main game loop: poll all active creatures forever.

    Combat rounds use initiative order. Peaceful creatures use default order.
    Each iteration advances time by one round (6 seconds).
    """
    entities_layer = get_entities_layer(world)

    while True:
        creatures = entities_layer.get_active_creatures()
        if not creatures:
            break

        # Combat rounds: iterate by initiative order
        for region_id in list(entities_layer.get_combat_regions()):
            combat = entities_layer.get_combat(region_id)
            if not combat:
                continue
            for entity_id in list(combat.turn_order):
                entity = entities_layer.get_entity(entity_id)
                if isinstance(entity, Creature) and entity.is_alive and entity.active and entity.in_combat:
                    entity.take_turn(world)
            # End of round — check for combat exit
            entities_layer.end_combat_round(region_id)

        # Peaceful turns: creatures not in combat
        for creature in creatures:
            if creature.in_combat or not creature.is_alive or not creature.active:
                continue
            creature.take_turn(world)

        world.advance_time(TimeDelta.from_rounds(1))
