"""Geography layer — the physical world.

Simulates the aspects of reality that exist independent of civilization:
- Regions with coordinates (latitude/longitude), elevation, terrain types
- Weather via Markov chains with modifiers (season, terrain, altitude, water proximity)
- Temperature from formulas (latitude + elevation + season + time of day)
- Day/night cycle and daylight duration from latitude and time of year

This is the lowest simulation layer. It has no dependencies on other layers.
"""
