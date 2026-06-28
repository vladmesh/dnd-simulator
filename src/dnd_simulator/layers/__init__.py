"""Concrete simulation layer implementations.

Each sub-package is an independent layer in the simulation stack.
Layers are ordered by abstraction level — each depends only on layers below it:

- geography: physical world (terrain, weather, day/night, coordinates)
- politics: factions, borders, diplomacy, laws
- settlements: towns, local economy, population dynamics
- ecology: squad movement, lairs, abstract world simulation
- entities: all tracked creatures — player, NPCs, named monsters

Layers share a common interface (tick, handle_event, query) defined in core.layer.
"""
