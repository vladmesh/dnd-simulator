# D&D Simulator

Text RPG with multi-level LLM simulation, inspired by classic text adventures and powered by modern language models.

An LLM-powered Dungeon Master orchestrates a layered world simulation where each layer builds on top of the previous one — from geography and weather up to individual NPC conversations.

See [ARCHITECTURE.md](ARCHITECTURE.md) for details on how the system is structured.

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
make install    # install dependencies
make check      # run all checks (lint + typecheck + test)
make format     # auto-format code
make test       # run tests only
```
