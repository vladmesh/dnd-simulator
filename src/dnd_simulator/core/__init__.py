"""Foundation of the simulation engine.

Defines the core abstractions that everything else builds on:
- GameDateTime, TimeDelta — in-game time representation
- Event, Query, Answer — communication protocol between layers
- Layer — abstract base class for all simulation layers
- World — container that holds layers, manages global time, and propagates events

This module has no external dependencies. All other modules depend on it.
"""
