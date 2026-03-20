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

# Single test file
uv run pytest tests/test_character.py

# Single test
uv run pytest tests/test_character.py::TestPerceive::test_perceive_character_sees_race

# Tests with coverage
uv run pytest --cov=src/dnd_simulator
```

## Architecture

Layered LLM-powered text RPG simulator built on a **layer stack** pattern. Each layer simulates one aspect of the world through an identical `Layer` ABC interface (`tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`).

### Layer Stack (order = dependency direction, lower layers know nothing about upper ones)

1. **Geography** (`layers/geography/`) — terrain, coordinates, weather, day/night cycle. Ticks every call.
2. **Politics** (`layers/politics/`) — nations, diplomacy, warfare, economy. Ticks every 30 in-game days.
3. **Settlements** (`layers/settlements/`) — towns, population, prosperity, harvests. Ticks every 30 in-game days.
4. **NPCs** (`layers/npcs/`) — individual characters with daily schedules and LLM-powered dialog. Ticks every call (activity updates driven by hour of day).

### Module Dependency Flow

```
core/              — models, Layer ABC, World, Entity/Character hierarchy (no deps)
  ↓
layers/            — concrete layer implementations (depend on core only)
  ↓
service.py         — GameService: transport-agnostic API, command routing
  ↓
adapters/          — CLI REPL (future: API, Telegram)

rules/             — pure D&D mechanics functions (no deps)
llm/               — thin OpenAI-compatible client wrapper (OpenRouter)
storage/           — SaveStore interface, JsonFileStore
content_loader.py  — loads worlds, nations, settlements, NPCs, player from YAML
content/           — YAML world definitions (data, not code)
```

### Key Design Principles

- **Layers depend down, never up.** Geography never imports from NPCs.
- **Rules are pure functions** in `rules/` and layer-specific `formulas.py` — no state, no I/O.
- **LLM is injected** — layers receive an LlmClient, never instantiate one.
- **Content is data** — worlds, NPCs, quests defined in YAML under `content/`.
- **Transport is thin** — adapters only translate I/O, all logic lives in `GameService`.

### Time System

`GameDateTime` uses a 30-day/month, 12-month/year calendar. `TimeDelta` measures in seconds; 1 D&D round = 6 seconds. `World.advance_time(delta)` ticks only layers whose `tick_interval` has elapsed.

### Entity Hierarchy

`Entity` → `Character` (D&D ability scores, race, class, alignment, HP) → `PlayerCharacter` / `Npc`. The `perceive()` method controls what information an observer sees about a target — LLM prompts never receive raw character data.

## Code Style

- Python 3.12+, strict mypy, ruff with 120-char line length
- Cyrillic characters allowed (Russian localization in game text)
- Frozen dataclasses for models; `object` (not `Any`) in state dicts for mypy strict
- Each layer has: `layer.py` (Layer impl), `models.py` (data), `formulas.py` (pure math)
- Tests mirror source structure: `test_{layer}_layer.py`, `test_{layer}_formulas.py`

## Environment

- Requires `.env` with `OPENROUTER_API_KEY` for LLM features
- Default LLM model: `deepseek/deepseek-chat-v3-0324`
- Save files: `saves/` directory (JSON)
