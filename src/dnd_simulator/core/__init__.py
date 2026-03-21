"""Foundation of the simulation engine.

Defines the core abstractions that everything else builds on:
- GameDateTime (second precision), TimeDelta (seconds-based, with round/hour/day factories)
- Event, Query, Answer, ActionResult — communication protocol between layers
- Layer — abstract base class with tick_interval for all simulation layers
- World — container that holds layers, manages per-layer tick scheduling, and propagates events
- Entity → Creature (in_combat flag, brain) → Character hierarchy with activation, D&D ability scores, and perception
- Action — transport-agnostic creature action (name + params)
- Brain ABC, RuleBrain — strategy pattern for creature decision-making (utility-scoring combat AI, canned dialogue)
- CombatState — tracks initiative order, round number, and auto-exit counter per location
- BattleMap, Position, Wall — 2D combat grid with entity positions, wall collision, random placement
- Location, LocationEdge, LocationGraph — flat navigation graph mapping locations to regions/settlements
- build_awareness / build_combat_awareness — two context modes for peaceful and combat turns

This module has no external dependencies (except i18n for translatable strings).
All other modules depend on it.
"""
