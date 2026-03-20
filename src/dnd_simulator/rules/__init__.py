"""Pure functions for game mechanics and world formulas.

Stateless calculations that can be used by any layer or the Master:
- dice: atomic dice rolling (roll("2d6+3"), roll_d20 with advantage/disadvantage)
- checks: D&D 5e check mechanics (attack_roll, ability_check, saving_throw, damage_roll)
- geography: temperature, daylight, travel time, distance calculations
- politics: warfare, trade, stability, diplomacy formulas
- settlements: harvest, population growth, conquest effects

All functions are pure — no side effects, no state, no LLM calls.
Easy to test in isolation.
"""
