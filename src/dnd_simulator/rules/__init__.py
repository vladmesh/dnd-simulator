"""Pure functions for game mechanics and world formulas.

Stateless calculations that can be used by any layer or the Master:
- dnd: D&D 5e mechanics (dice rolls, skill checks, combat resolution)
- physics: temperature from latitude/elevation, daylight duration, tides
- economics: supply/demand, price calculations, trade route profitability

All functions are pure — no side effects, no state, no LLM calls.
Easy to test in isolation.
"""
