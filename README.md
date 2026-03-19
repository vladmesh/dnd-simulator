# D&D Simulator

Text RPG with multi-level LLM simulation, inspired by classic text adventures and powered by modern language models.

## Concept

A layered world simulation where each layer builds on top of the previous one:

- **Geography** — physical world, weather, terrain, day/night cycle
- **Politics & Economy** — factions, trade routes, borders
- **Settlements** — towns and villages with internal life simulation
- **NPCs** — individual characters as LLM agents

An LLM-powered Dungeon Master orchestrates everything: describes the world, interprets player actions, manages time flow, and synchronizes layers.

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
make install    # install dependencies
make check      # run all checks (lint + typecheck + test)
make format     # auto-format code
make test       # run tests only
```
