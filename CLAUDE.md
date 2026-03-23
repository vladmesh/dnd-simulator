# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install      # uv sync — install all dependencies
make check        # lint + typecheck + test (full CI validation)
make test         # uv run pytest
make lint         # ruff check + format check
make format       # auto-fix formatting and lint issues
make typecheck    # uv run mypy src/
make messages     # extract translatable strings to .pot
make compile-messages  # compile .po → .mo
make serve        # uvicorn API server on :8001 with --reload (auto-builds frontend if node_modules exist)
make frontend-dev  # vite dev server for frontend
make frontend-build # build frontend for production

# Single test file
uv run pytest tests/test_character.py

# Single test
uv run pytest tests/test_character.py::TestPerceive::test_perceive_character_sees_race

# Tests with coverage
uv run pytest --cov=src/dnd_simulator
```

## Product Vision

See [docs/VISION.md](docs/VISION.md) for product vision and [docs/ROADMAP.md](docs/ROADMAP.md) for current status and plans.

## Architecture

Layered LLM-powered text RPG simulator built on a **layer stack** pattern. Each layer simulates one aspect of the world through an identical `Layer` ABC interface (`tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`).

### Layer Stack (order = dependency direction, lower layers know nothing about upper ones)

1. **Geography** (`layers/geography/`) — terrain, coordinates, weather, day/night cycle. Ticks every call.
2. **Politics** (`layers/politics/`) — nations, diplomacy, warfare, economy. Ticks every 30 in-game days.
3. **Settlements** (`layers/settlements/`) — towns, population, prosperity, harvests. Ticks every 30 in-game days.
4. **Entities** (`layers/entities/`) — all tracked creatures: player, NPCs, named monsters. Tick is a no-op; the Round orchestrator drives all creature turns.

### Module Dependency Flow

```
core/              — models, Layer ABC, World, Entity/Character hierarchy (no deps)
  ↓
layers/            — concrete layer implementations (depend on core only)
  ↓
round.py           — Round orchestrator: multi-action turn loop with budget enforcement
service/           — GameService + command modules (combat, creatures, politics, save, time, world)
  ↓
adapters/          — FastAPI REST + WebSocket API

rules/             — pure D&D mechanics functions (no deps)
llm/               — LLM client, prompt builders, tool schemas (OpenRouter)
storage/           — SaveStore interface, JsonFileStore
content_loader.py  — loads worlds, nations, settlements, NPCs, player from YAML
content/           — YAML world definitions (data, not code)
frontend/          — React + TypeScript SPA (Vite, shadcn/ui, Zustand)
```

### Key Design Principles

- **Layers depend down, never up.** Geography never imports from NPCs. Enforced at runtime: `query_fn` and `emit_fn` callbacks injected by World validate direction — layers can only query layers below them.
- **Rules are pure functions** in `rules/` — no state, no I/O.
- **Brain is a strategy** — `Creature.brain` field holds a `Brain` (RuleBrain or LlmBrain), decoupling AI from entity type.
- **LLM is injected** — `LlmBrain` wraps an `LlmClient`; rule-based NPCs use `RuleBrain` with zero LLM calls.
- **Content is data** — worlds, NPCs, quests defined in YAML under `content/`. Two formats: legacy single-file and directory (world.yaml, regions.yaml, nations.yaml, npcs.yaml, locations.yaml).
- **Transport is thin** — adapters only translate I/O, all logic lives in `GameService`.
- **Two editing modes** — between sessions: edit YAML files on disk; during session: hot controls in memory (creature spawn/delete, HP, brain, time).

### Time System

`GameDateTime` uses a 30-day/month, 12-month/year calendar. `TimeDelta` measures in seconds; 1 D&D round = 6 seconds. `World.advance_time(delta)` ticks only layers whose `tick_interval` has elapsed.

### Entity Hierarchy

`Entity` (id, name, location_id, active, on_tick) → `Creature` (ability scores, HP, AC, in_combat, is_dodging, brain) → `Character` (race, class, alignment) → `PlayerCharacter` / `Npc`. Creature delegates decisions to `brain.choose_action()` and executes via `execute_action()`. The `perceive()` method controls what information an observer sees about a target — LLM prompts never receive raw character data. All tracked entities live on the `EntitiesLayer`. `World.location_graph` (`LocationGraph`) maps locations to regions/settlements; entities reference `location_id`, and the graph resolves which region/settlement a location belongs to. NPCs have structured memory (`NpcMemory`: tags, recent, inner_state, current_conversation) readable by both LLM and RuleBrain; a `MemorySummarizer` compresses events into memory via LLM after combat/conversation ends. Combat is managed via `CombatState` (initiative order, round tracking, auto-exit after 2 idle rounds) and `BattleMap` (2D grid with positions, walls, and movement). Movement rules live in `rules/movement.py` (D&D 5e diagonal distance, wall collision, occupied-cell blocking).

### Multi-Action Turns

Each creature's turn is a multi-action loop orchestrated by `Round` (in `round.py`). A `TurnBudget` (actions, bonus_actions, movement_remaining, reaction) is created from creature stats at the start of each turn. The brain is called repeatedly: choose action → check budget via `action_cost()` (in `rules/actions.py`) → execute → rebuild awareness → repeat, until the brain returns `end_turn` or budget is exhausted. `PlayerBrain` uses a queue + callback pattern for interactive I/O.

## Code Style

- Python 3.12+, strict mypy, ruff with 120-char line length
- All user-visible strings use `gettext` via `from dnd_simulator.i18n import _`; English base, Russian `.po` translation
- Frozen dataclasses for models; `object` (not `Any`) in state dicts for mypy strict
- Each layer has: `layer.py` (Layer impl), `models.py` (data); pure math lives in `rules/`
- Tests mirror source structure: `test_{layer}_layer.py`, `test_{layer}_formulas.py`

## Environment

- Requires `.env` with `OPENROUTER_API_KEY` for LLM features (only if NPCs use `ai: llm`)
- Default LLM model: `deepseek/deepseek-chat-v3-0324`
- `DND_LANGUAGE` env var selects game language (default: `ru`); locale files in `src/dnd_simulator/locale/`
- Save files: `saves/` directory (JSON)
- API: `make serve` → http://localhost:8001/docs (Swagger UI)
