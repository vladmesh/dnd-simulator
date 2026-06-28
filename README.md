# D&D Simulator

Text RPG with multi-level LLM simulation, inspired by classic text adventures and powered by modern language models.

An LLM-powered Dungeon Master orchestrates a layered world simulation where each layer builds on top of the previous one — from geography and weather up to individual NPC conversations.

See [ARCHITECTURE.md](ARCHITECTURE.md) for details on how the system is structured.
See [docs/VISION.md](docs/VISION.md) for product vision and [docs/ROADMAP.md](docs/ROADMAP.md) for current status and plans.

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Frontend requires Node.js 18+.

```bash
make install        # install Python dependencies
make check          # backend + frontend lint/typecheck/test (CI minus integration)
make format         # auto-format code
make test           # run tests only
make serve          # start API server on :8001 (auto-builds frontend)
make frontend       # start Vite dev server for frontend
```
