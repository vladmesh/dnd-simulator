"""Foundation of the simulation engine.

Defines the core abstractions that everything else builds on:
- GameDateTime (second precision), TimeDelta (seconds-based, with round/hour/day factories)
- Event, Query, Answer, ActionResult — communication protocol between layers
- Layer — abstract base class with tick_interval for all simulation layers
- World — container that holds layers, manages per-layer tick scheduling, and propagates events
- Entity → Creature (in_combat flag) → Character hierarchy with activation, D&D ability scores, and perception
- CombatState — tracks initiative order, round number, and auto-exit counter per region
- BattleMap, Position, Wall — 2D combat grid with entity positions, wall collision, random placement
- build_awareness / build_combat_awareness — two context modes for peaceful and combat turns

This module has no external dependencies. All other modules depend on it.
"""
