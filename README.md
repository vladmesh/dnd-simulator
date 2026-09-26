# D&D Simulator

A text RPG set in a living fantasy world. It uses D&D 5e rules, and the game handles all the bookkeeping for you. You don't need to know the rules, gather a group or find a dungeon master.

The world is a stack of simulation layers: geography and weather, politics, settlements, ecology (monster squads and lairs), and individual creatures. Each layer ticks at its own rate, and lower layers never depend on upper ones. Creatures act through swappable *brains*. A brain can be rule-based utility scoring (no LLM calls at all), an LLM, or a human player. The engine treats all of them the same way.

Currently implemented:

- turn-based D&D 5e combat on a grid battle map: initiative, multi-action turns (action / bonus action / movement / reaction), opportunity attacks, conditions, fleeing a scene
- Fighter, Rogue and Paladin with level-1/level-2 class features, XP and level-up
- SRD weapons, armor, shields and accessories, inventory, trading, loot
- factions, reputation and combat sides; lairs, random encounters by location and time of day
- NPC "inner self" (relations, mood, goals, drifting alignment), digested by rules or, for LLM-driven NPCs, by the model
- versioned saves with reproducible world and dice seeds
- a web UI with a player screen and a game-master screen (world editor built from reusable content templates, live session controls)
- English and Russian localisation (Russian is the default)

The game is fully playable without any LLM. An OpenRouter key only adds LLM-driven NPCs.

Work in progress: expect rough edges. See [docs/VISION.md](docs/VISION.md) for where the project is going and [docs/ROADMAP.md](docs/ROADMAP.md) for what is planned next.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20.19+ or 22.12+ (required by Vite 8) for the web UI
- Docker with Compose, only for the integration tests
- `lsof`: `make serve` and `make clean` use it to free ports

## Quick start

```bash
make install                         # Python dependencies (uv sync)
(cd frontend && npm ci)              # frontend dependencies

make serve       # API on http://localhost:8001 (Swagger UI at /docs)
make frontend    # in another terminal: web UI on http://localhost:5173
```

Open http://localhost:5173 and pick **Player** to create a character and start a session, or **Master** to browse and edit worlds. The Vite dev server proxies `/api` (including the WebSocket) and `/health` to port 8001. `make up` starts both servers from a single terminal.

Game content (worlds, NPCs, monsters, items) is plain YAML under [`content/`](content/). The bundled world is `sword_vale`.

## Configuration

The server reads environment variables. A `.env` file in the working directory is loaded on startup.

| Variable | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Enables LLM-driven NPCs (`ai: llm` in content). Without it every NPC uses the rule-based brain. |
| `LLM_MODEL` | — | OpenRouter model id. Required when `OPENROUTER_API_KEY` is set. |
| `DND_LANGUAGE` | `ru` | Default game language (`ru` or `en`). |
| `DND_CONTENT_DIR` | `content/` | Directory with worlds, library templates and catalogs. |
| `DND_WORLD_SEED` | random (logged) | Seed for the world simulation layers. |
| `DND_DICE_SEED` | random | Initial seed for each session's dice. |
| `DND_AUTOSAVE_SECONDS` | `120` | Periodic autosave interval. Must be greater than 0. |
| `DND_ROUND_STOP_TIMEOUT_SECONDS` | `5` | How long load or eviction waits for the round thread to stop. |
| `DND_EVICT_GRACE_SECONDS` | `1.5` | How long a session waits after the last player disconnects before it is saved and unloaded. |
| `LOG_LEVEL` | `WARNING` | Log level. `DEBUG` on a TTY gives pretty console output. |
| `LOG_DIR` | — | With `LOG_LEVEL=DEBUG`, also writes per-session JSONL logs here (see [docs/LOGGING.md](docs/LOGGING.md)). |
| `CORS_ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins for the REST API. |
| `WS_ALLOWED_ORIGINS` | any | Comma-separated origins allowed to open the game WebSocket. |

Saves are JSON files in `saves/`.

## Development

```bash
make check              # backend + frontend lint, type check and unit tests (CI minus integration)
make check-backend      # ruff + mypy (strict) + pytest
make check-frontend     # eslint + tsc -b + vitest
make test               # pytest (unit tests)
make test-integration   # backend + integration tests in Docker Compose
make format             # auto-format and auto-fix Python code
make setup-hooks        # install pre-commit (format) and pre-push (scope-filtered check) git hooks
make messages           # extract translatable strings to .pot
make compile-messages   # compile .po → .mo
make clean              # stop dev servers, wipe saves/ and logs/
```

Frontend type checking uses `tsc -b` so that the referenced projects (app, tests, Vite config) are all checked. `tsc --noEmit` against the root `frontend/tsconfig.json` checks nothing. `cd frontend && npm run build` runs the same type check before bundling.

CI (GitHub Actions) runs the backend checks, the frontend checks and the integration tests. It skips the halves a change doesn't touch.

## Project layout

```
src/dnd_simulator/
  core/            models, Layer interface, World, entity hierarchy, brains
  layers/          geography, politics, settlements, ecology, entities
  rules/           pure D&D mechanics (combat, movement, leveling, loot, ...)
  round.py         turn loop: multi-action turns with budget enforcement
  service/         GameService: sessions, commands, action dispatch
  adapters/api/    FastAPI REST + WebSocket
  llm/             OpenRouter client, LLM brain, prompts, tools
  storage/         versioned JSON saves
  content_loader/  YAML loading, content schemas, world assembly
content/           worlds, reusable layer templates, item and monster catalogs
frontend/          React + TypeScript web UI (Vite, shadcn/ui, Zustand)
tests/             unit and integration tests
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the pieces fit together.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): system design, module map, data flow
- [docs/VISION.md](docs/VISION.md): product vision (in Russian)
- [docs/ROADMAP.md](docs/ROADMAP.md): planned work (in Russian)
- [docs/LOGGING.md](docs/LOGGING.md): structured logging and log files
- [docs/e2e-playbook.md](docs/e2e-playbook.md): manual/browser end-to-end regression scenarios
- [AGENTS.md](AGENTS.md): instructions for AI coding agents working in this repository
