"""Foundation of the simulation engine.

Defines the core abstractions that everything else builds on:
- GameDateTime (second precision), TimeDelta (seconds-based, with round/hour/day factories)
- Event, Query, Answer — communication protocol between layers
- Layer — abstract base class with tick_interval for all simulation layers
- World — container that holds layers, manages per-layer tick scheduling, and propagates events
- Entity → Creature → Character hierarchy with activation, D&D ability scores, and perception

This module has no external dependencies. All other modules depend on it.
"""
