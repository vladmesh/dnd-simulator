"""Main game loop — polls all active creatures in turn order."""

from __future__ import annotations

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

    Each creature calls take_turn(world), which:
    - builds its own awareness
    - decides an action (LLM / player input / if-else)
    - executes it through world.handle_event

    Region logs persist as history — each creature tracks its own read index.
    """
    entities_layer = get_entities_layer(world)

    while True:
        creatures = entities_layer.get_active_creatures()
        if not creatures:
            break

        for creature in creatures:
            if not creature.is_alive or not creature.active:
                continue
            creature.take_turn(world)
