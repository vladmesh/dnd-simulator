# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install      # uv sync — install all dependencies
make check        # lint + typecheck + test (full CI validation)
make test         # uv run pytest (all tests)
make test-unit    # uv run pytest tests/unit/ (fast, no I/O)
make test-integration  # docker compose — backend + integration tests
make lint         # ruff check + format check
make format       # auto-fix formatting and lint issues
make typecheck    # uv run mypy src/
make setup-hooks  # install pre-commit (auto-format) and pre-push (check) hooks
make messages     # extract translatable strings to .pot
make compile-messages  # compile .po → .mo
make serve        # uvicorn API server on :8001 with --reload
make frontend     # vite dev server on :5173, proxies /api → :8001

# Single test file
uv run pytest tests/unit/test_character.py

# Single test
uv run pytest tests/unit/test_character.py::TestPerceive::test_perceive_character_sees_race

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
4. **Ecology** (`layers/ecology/`) — squad movement, abstract world simulation. Ticks every hour.
5. **Entities** (`layers/entities/`) — all tracked creatures: player, NPCs, named monsters. Tick is a no-op; the Round orchestrator drives all creature turns.

### Module Dependency Flow

```
core/              — models, Layer ABC, World, Entity/Character hierarchy, Condition, Item, ClassFeatures, ResourcePool, ActionDef (no deps)
  ↓
layers/            — concrete layer implementations (depend on core only)
  ↓
round.py           — Round orchestrator: multi-action turn loop with budget enforcement
service/           — GameService, ActionDispatcher, BrainFactory, command modules
  ↓
adapters/          — FastAPI REST + WebSocket API

rules/             — pure D&D mechanics: combat, validation, conditions, weapons, modifiers, proficiency, sneak attack, resources, action providers, handlers/ package (no deps)
llm/               — LLM client, prompt builders, tool schemas (OpenRouter)
storage/           — SaveStore interface, JsonFileStore
content_loader/    — loads worlds, nations, settlements, NPCs, player from YAML; manifest resolver, library catalog, world assembly
content/           — YAML world definitions (data, not code); library/ (reusable layer templates), worlds/ (manifest + optional custom layers)
frontend/          — React + TypeScript SPA (Vite, shadcn/ui, Zustand)
```

### Key Design Principles

- **Layers depend down, never up.** Geography never imports from NPCs. Enforced at runtime: `query_fn` and `emit_fn` callbacks injected by World validate direction — layers can only query layers below them.
- **Rules are pure functions** in `rules/` — no state, no I/O.
- **Brain is a strategy** — `Creature.brain` field holds a `Brain` (RuleBrain or LlmBrain), decoupling AI from entity type.
- **LLM is injected** — `LlmBrain` wraps an `LlmClient`; rule-based NPCs use `RuleBrain` with zero LLM calls.
- **Content is data** — worlds, NPCs, quests defined in YAML under `content/`. Library templates in `content/library/{layer_type}/{slug}/` with `metadata.yaml`. Worlds in `content/worlds/{id}/manifest.yaml` referencing library templates or custom layers. Fork (copy to custom) for editing.
- **Transport is thin** — adapters only translate I/O, all logic lives in `GameService`.
- **Two editing modes** — between sessions: edit YAML files on disk; during session: hot controls in memory (creature spawn/delete, HP, brain, time).

### Time System

`GameDateTime` uses a 30-day/month, 12-month/year calendar. `TimeDelta` measures in seconds; 1 D&D round = 6 seconds. `World.advance_time(delta)` ticks only layers whose `tick_interval` has elapsed.

### Entity Hierarchy

`Entity` (id, name, location_id, active, on_tick) → `Creature` (ability scores, HP, AC, in_combat, is_dodging, wake_at_seconds, brain, equipped_armor, equipped_shield, resource_pools) → `Character` (race, class, alignment, class_features) → `PlayerCharacter` / `Npc`. Creature delegates decisions to `brain.choose_action()` and executes via `execute_action()`. The `perceive()` method controls what information an observer sees about a target — LLM prompts never receive raw character data. All tracked entities live on the `EntitiesLayer`. `World.location_graph` (`LocationGraph`) maps locations to regions/settlements; entities reference `location_id`, and the graph resolves which region/settlement a location belongs to. NPCs have structured memory (`NpcMemory`: tags, recent, inner_state, current_conversation) readable by both LLM and RuleBrain; a `MemorySummarizer` compresses events into memory via LLM after combat/conversation ends. Combat is managed via `CombatState` (initiative order, round tracking, auto-exit after 2 idle rounds) and `BattleMap` (2D grid with positions, walls, and movement). Movement rules live in `rules/movement.py` (D&D 5e diagonal distance, wall collision, occupied-cell blocking).

### Multi-Action Turns

Each creature's turn is a multi-action loop orchestrated by `Round` (in `round.py`). A `TurnBudget` (actions, bonus_actions, movement_remaining, reaction) is created from creature stats at the start of each turn. The brain is called repeatedly: choose action → `ActionDispatcher` validates (budget, target, reach via `rules/validation.py`) → executes handler (`rules/handlers/`) → rebuilds awareness → repeat, until the brain returns `end_turn` or budget is exhausted. `ActionProvider` (`rules/action_provider.py`) determines which actions are currently available to a creature. `PlayerBrain` uses a queue + callback pattern for interactive I/O.

### Conditions & Items

D&D 5e conditions (`core/conditions.py`) — `Condition` enum + `ConditionsMap` (condition → remaining rounds or permanent). Pure mechanics in `rules/conditions.py`: `is_incapacitated()`, `effective_speed()`, `attack_advantage()`. Conditions tick down at turn start; weapons can grant permanent conditions while equipped.

Items (`core/items.py`) — `Item` with `ItemType` (WEAPON, POTION, ARMOR, SHIELD). `WeaponDef` defines attack name, damage, reach, ability, magic bonus, finesse, category, and can grant conditions/actions. `ArmorDef` defines base AC, DEX cap, armor category (light/medium/heavy). `ShieldDef` defines AC bonus. `rules/weapons.py`: `get_weapon_attack()` builds `Attack` from equipped weapon or falls back to creature attacks / unarmed strike. `rules/proficiency.py`: weapon/armor proficiency per class, proficiency bonus by level. Equip/unequip actions swap `equipped_weapon`/`equipped_armor`/`equipped_shield` from inventory.

### Class Features & Resources

Composition-based class mechanics (`core/class_features.py`). Each D&D class gets a frozen dataclass (`FighterFeatures`, `RogueFeatures`). `Character.class_features: list[ClassFeatures]` — multiclass gets multiple entries. `get_feature(FeatureType)` retrieves by type. Features define class-specific data consumed by `rules/`: Fighting Styles (Defense +1 AC, Dueling +2 damage) via modifier pipeline, Sneak Attack dice count, Cunning Action cost overrides (Dash/Disengage as bonus action).

Resource pools (`core/resource.py`) — `ResourcePool(id, max_uses, current_uses, reset_on)` on `Creature.resource_pools`. `RestType` (SHORT_REST, LONG_REST) controls when pools reset. Used for Second Wind (1/short rest), future spell slots. Pure functions in `rules/resources.py`.

Action definitions (`core/action_defs.py`) — centralized `ActionDef` registry: cost, params, combat mode, flags per `ActionType`. `CostOverride` allows class features to change action costs (e.g. Cunning Action makes Dash a bonus action).

### Modifier Pipeline

Centralized derived stat computation (`core/modifiers.py` data types, `rules/modifiers.py` pure functions). Modifiers represent effects on creature stats from conditions, equipment, spells, and class features. Each modifier has a `StatType` (AC, speed, attack_roll, initiative), a `ModifierOp` (ADD, OVERRIDE, ADVANTAGE, DISADVANTAGE), and an optional source (same source doesn't stack per D&D 5e). The pipeline collects modifiers from all sources via `collect_self_modifiers()` / `collect_defense_modifiers()`, then computes effective values: `effective_speed()`, `effective_ac()`, `attack_modifiers()`. Replaces ad-hoc stat computation that was scattered across combat_manager and conditions.

### Activation & Fast-Forward

Proximity-based activation: `EntitiesLayer.update_activation(time)` runs at the start of each round. Players without `wake_at_seconds` are anchors — creatures at an anchor's location become active, all others go dormant. Creatures in combat stay active regardless. `wait` action sets `creature.wake_at_seconds` and marks it dormant. When no active creatures exist, `Round.run_loop()` fast-forwards time to the nearest `wake_at`, then re-checks activation. Content requires explicit locations — no auto-generation from regions.

## Code Style

- Python 3.12+, strict mypy, ruff with 120-char line length
- All user-visible strings use `gettext` via `from dnd_simulator.i18n import _`; English base, Russian `.po` translation
- Frozen dataclasses for models; `object` (not `Any`) in state dicts for mypy strict
- Each layer has: `layer.py` (Layer impl), `models.py` (data); pure math lives in `rules/`
- Tests mirror source structure: `test_{layer}_layer.py`, `test_{layer}_formulas.py`

## Environment

- Requires `.env` with `OPENROUTER_API_KEY` for LLM features (only if NPCs use `ai: llm`)
- `LLM_MODEL` env var selects model (required if `OPENROUTER_API_KEY` is set, no default)
- `DND_LANGUAGE` env var selects game language (default: `ru`); locale files in `src/dnd_simulator/locale/`
- Save files: `saves/` directory (JSON)
- Backend API: `make serve` → http://localhost:8001/docs (Swagger UI)
- Frontend: `make frontend` → http://localhost:5173 (entry point, proxies /api to :8001)
