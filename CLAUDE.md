# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install      # uv sync — install all dependencies
make check        # backend + frontend lint/typecheck/test (mirrors CI minus integration)
make check-backend    # lint + typecheck + test (backend half of `check`)
make check-frontend   # lint-frontend + typecheck-frontend + test-frontend (frontend half of `check`)
make test         # uv run pytest (all tests)
make test-unit    # uv run pytest tests/unit/ (fast, no I/O)
make test-integration  # docker compose — backend + integration tests
make lint         # ruff check + format check
make format       # auto-fix formatting and lint issues
make typecheck    # uv run mypy src/
make setup-hooks  # install pre-commit (auto-format) and pre-push (scope-filtered check) hooks
make messages     # extract translatable strings to .pot
make compile-messages  # compile .po → .mo
make serve        # uvicorn API server on :8001 with --reload
make frontend     # vite dev server on :5173, proxies /api → :8001
make clean        # kill dev processes, wipe saves/logs/screenshots

# Single test file
uv run pytest tests/unit/test_character.py

# Single test
uv run pytest tests/unit/test_character.py::TestPerceive::test_perceive_character_sees_race

# Tests with coverage
uv run pytest --cov=src/dnd_simulator
```

## Running tests — ALWAYS log to a file

Never run `make test`, `make test-unit`, `make test-integration`, or `make check` without redirecting output to a file. Reruns to re-read different sections of the same output cost minutes each and are forbidden.

```bash
make test-integration 2>&1 | tee /tmp/integration.log
make check 2>&1 | tee /tmp/check.log
```

Then use the Read tool on the log file to inspect any section. If nothing changed, don't rerun — re-read the saved log.

## Pre-push hook scope filter

`.githooks/pre-push` classifies the files being pushed via `scripts/classify-scope.sh` (the same classifier CI's `detect-changes` job uses) and runs only the relevant half: frontend-only changes run `make check-frontend`, backend-only run `make check-backend`, docs-only run nothing, anything mixed or touching infra (Makefile, scripts/, .github/, orca.yaml, docker*, ...) runs the full `make check`. Any classification error or empty input also falls back to the full `make check`. After pulling changes to the hook scripts, re-run `make setup-hooks` to pick them up.

## Process

Sprints run on the secretary board, not in this repo: see [docs/SPRINT_PIPELINE.md](docs/SPRINT_PIPELINE.md).

This repository holds no state file and no backlog file (since 2026-09-21):

- **Current state and what hurts** — the board: `issue list --product dnd-simulator`,
  `sprint list --status open`, `task list --project dnd-simulator`. Bugs, tech debt, test gaps and
  feature candidates are issues of the `dnd-simulator` product.
- **History, design and decisions** — knowledge of the secretary instance,
  `state/knowledge/projects/dnd-simulator/`: `README.md` (entry point), `brainstorms/` (live design
  documents, e.g. `simulation-core.md`), `archive/` (implemented/cancelled documents and snapshots of
  the former `BACKLOG.md`, `STATUS.md`, `audit.md`), `decisions/`, `sprints/001-024`, `e2e-reports/`.
- **Never create** `BACKLOG.md`, `STATUS.md`, `audit.md` or any similar state/backlog file here, and
  do not restore the deleted ones. If a card spec asks for it, report that back instead of doing it;
  findings go into the worker report and the PO turns them into issues.

Commit messages carry no AI co-authorship trailers.

## Product Vision

See [docs/VISION.md](docs/VISION.md) for product vision and [docs/ROADMAP.md](docs/ROADMAP.md) for what is still planned.

## Architecture

Layered LLM-powered text RPG simulator built on a **layer stack** pattern. Each layer simulates one aspect of the world through an identical `Layer` ABC interface (`tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`).

### Layer Stack (order = dependency direction, lower layers know nothing about upper ones)

1. **Geography** (`layers/geography/`) — terrain, coordinates, weather, day/night cycle. Ticks every call.
2. **Politics** (`layers/politics/`) — nations, diplomacy, warfare, economy, faction relations. Ticks every 30 in-game days. Split into submodules: `diplomacy.py`, `warfare.py`, `economy.py`.
3. **Settlements** (`layers/settlements/`) — towns, population, prosperity, harvests. Ticks every 30 in-game days.
4. **Ecology** (`layers/ecology/`) — squad movement, lairs, abstract world simulation. Ticks every hour.
5. **Entities** (`layers/entities/`) — all tracked creatures: player, NPCs, named monsters, plus `Container` loot objects. Tick is a no-op; the Round orchestrator drives all creature turns.

### Module Dependency Flow

```
core/              — models, Layer ABC, World, Entity/Character hierarchy, Container, Lair, InventoryHolder, Condition, Item, ClassFeatures, ResourcePool, ActionDef, TimeOfDay (no deps)
  ↓
layers/            — concrete layer implementations (depend on core only, except entities' optional runtime LLM digest bridge, which imports `llm` only to recognize `LlmBrain` and invoke its injected client)
  ↓
round.py           — Round orchestrator: multi-action turn loop with budget enforcement
service/           — GameService, ActionDispatcher, BrainFactory, command modules
  ↓
adapters/          — FastAPI REST + WebSocket API

rules/             — pure D&D mechanics: combat, validation, conditions, weapons, modifiers, proficiency, sneak attack, divine smite, fighting style, resources, character creation (point buy, HP, starting equipment), leveling (XP-by-CR, thresholds), perform_level_up, action providers, handlers/ package, reputation, combat_sides, encounters (time-of-day gate), inventory (transfer_items), loot, inner-self digestion and alignment shift, rule_brain (no deps)
llm/               — LLM client, prompt builders, tool schemas (OpenRouter)
storage/           — SaveStore interface, JsonFileStore, versioned save schema (SaveGame, schema_version=2, world seed + RNG state в сейве; v1 migrates on load)
content_loader/    — loads worlds, nations, settlements, NPCs, player from YAML; Pydantic content schemas, JSON Schema generation, entity CRUD, manifest resolver, library catalog, world assembly, catalog loader (monsters/items)
content/           — YAML world definitions (data, not code); library/ (reusable layer templates), worlds/ (manifest + optional custom layers)
frontend/          — React + TypeScript SPA (Vite, shadcn/ui, Zustand)
```

### Key Design Principles

- **Layers depend down, never up.** Geography never imports from NPCs. Enforced at runtime: `query_fn` and `emit_fn` callbacks injected by World validate direction — layers can only query layers below them.
- **Rules are pure functions** in `rules/` — no state, no I/O.
- **Brain is a strategy** — `Creature.brain` field holds a `Brain` (RuleBrain, LlmBrain, PlayerBrain), decoupling AI from entity type. `BrainType(StrEnum)` in `core/brain.py` is the persisted discriminator; `RuleBrain` lives in `rules/rule_brain.py` so `core/` never imports concrete brains.
- **LLM is injected** — `LlmBrain` wraps an `LlmClient`; rule-based NPCs use `RuleBrain` with zero LLM calls.
- **Content is data** — worlds, NPCs, quests defined in YAML under `content/`. Library templates in `content/library/{layer_type}/{slug}/` with `metadata.yaml`. Worlds in `content/worlds/{id}/manifest.yaml` referencing library templates or custom layers. Fork (copy to custom) for editing.
- **Transport is thin** — adapters only translate I/O, all logic lives in `GameService`.
- **Two editing modes** — between sessions: edit YAML files on disk; during session: hot controls in memory (creature spawn/delete, HP, brain, time).

### Time System

`GameDateTime` uses a 30-day/month, 12-month/year calendar. `TimeDelta` measures in seconds; 1 D&D round = 6 seconds. `World.advance_time(delta)` ticks only layers whose `tick_interval` has elapsed.

### Entity Hierarchy

`Entity` (id, name, location_id, active, on_tick) → `Creature` (physical stats, combat state, `is_anchor`, persisted `current_intent`, brain, turn budget, equipment, resources and activation triggers) → `Character` (race, class, alignment, class features, level and XP) → `PlayerCharacter` / `Npc`. Creature delegates decisions to `brain.choose_action()`. Persistent non-player creatures with a brain carry `InnerSelf`: typed relations, one mood, goals, alignment accumulation, journal, bounded thoughts, and a persisted structured buffer of perceived events. Players and transient spawns do not carry `InnerSelf`. Active core-bearers collect through the event-log visibility filter without moving their brain cursor; one digest entry point consumes it at combat end, active → dormant, intent completion/interruption, or capacity. It first makes a pure rules proposal. Only `LlmBrain` then uses its own client to write a strictly validated replacement core and journal; a client or validation failure retains the proposal, and all other brains make no LLM call. `rules/inner_self_digest.py` treats positive law/chaos pressure as chaos and positive good/evil pressure as evil; each three evidence steps shifts a non-player `Character` one axis step, retains halved pressure below the threshold, and caps outward pressure at an edge. `Container` (`core/container.py`) is a separate `Entity` sibling of `Creature`: inventory + gold, no HP/turn/brain, used for lair treasuries and other lootable world objects (`EntityKind.CONTAINER`). The `perceive()` method controls what an observer sees; LLM prompts never receive raw character data. All tracked entities live on `EntitiesLayer`. `World.location_graph` maps locations to regions/settlements and supplies weighted routes for travel intents. RuleBrain reads mood and relations without changing combat sides. Combat is managed via `CombatState` and `BattleMap`; grid movement rules live in `rules/movement.py`.

### Multi-Action Turns

Each creature's turn is a multi-action loop orchestrated by `Round` (in `round.py`). A `TurnBudget` (actions, bonus_actions, movement_remaining, reaction) lives on `Creature.turn_budget` — persists between turns for reaction spending. Created fresh at the start of each creature's turn. The brain is called repeatedly: choose action → `ActionDispatcher` validates (budget, target, reach via `rules/validation.py`) → executes handler (`rules/handlers/`) → rebuilds awareness → repeat, until the brain returns `end_turn` or budget is exhausted. The dispatcher owns action, bonus action and reaction costs only. Movement is charged inside `rules/handlers/movement.py` by the distance actually moved, so `MOVE` and `MOVE_TO` are `CostType.FREE` at the dispatcher. `ActionProvider` (`rules/action_provider.py`) determines which actions are currently available to a creature. `PlayerBrain` uses a queue + callback pattern for interactive I/O.

### Reactions & Opportunity Attacks

D&D 5e reaction system. `Brain.choose_reaction(creature, trigger, available_reactions)` — unified method on ABC (RuleBrain: always attack, LlmBrain: LLM call, PlayerBrain: callback + queue). `ReactionTrigger` typed data object (extensible: `TriggerType.LEAVING_REACH` for OA, future: Counterspell, Shield). Movement handlers call `on_leave_reach` callback (injected via `ActionContext`) when a mover exits an enemy's reach. `check_reactions` in Round is recursive — a reaction can trigger another reaction, depth limited naturally (1 reaction per creature per round). `rules/reactions.py`: pure function `find_oa_triggers()`. OA handler in `rules/handlers/reactions.py`. Disengage sets `creature.is_disengaging = True` (reset at turn start), prevents OA. `Creature.combat_position` enables deterministic battle map placement from YAML/API.

### Flee (leaving the scene)

A location with an active `CombatState` is a scene; flee leaves both the fight and the scene. `rules/flee.py::flee_blocker`
is the one eligibility rule for every brain (enforced by `rules/validation.check_flee_allowed`): no living enemy within 15 ft
on the battle map and at least one neighbouring location — no roll. The player must name an adjacent `destination_id`; an
NPC's handler picks one by rule (towards its scheduled home, else away from enemies). `layers/entities/scene_exit.exit_scene`
is the single place a flee takes effect: the fleer leaves the combat (which ends if no opposing sides remain), then an
anonymous template spawn leaves the world (a squad/lair member is counted as a survivor at dematerialization), while a
named creature starts an ordinary one-edge `TravelIntent` and goes dormant (a named NPC gets `location_override`). The rest
of the fleer's turn may only re-plan that journey (`travel`). When a fight ends at a location no anchor holds, its random
encounter spawns dematerialize. `CombatAwareness.flee` (`FleeStatus`: `allowed`, `reason_key`, `reason`, `destinations`)
carries availability and the neighbour list to the player's UI.

### Conditions & Items

D&D 5e conditions (`core/conditions.py`) — `Condition` enum + `ConditionsMap` (condition → remaining rounds or permanent). Pure mechanics in `rules/conditions.py`: `is_incapacitated()`, `tick_conditions()`; condition effects on stats go through the modifier pipeline (`rules/modifiers.py`). Conditions tick down at turn start; weapons can grant permanent conditions while equipped.

Items (`core/items.py`) — `Item` with `ItemType` (WEAPON, POTION, ARMOR, SHIELD, ACCESSORY). `WeaponDef` defines attack name, damage, reach, ability, magic bonus, finesse, category, two-handed, light, heavy, and can grant conditions/actions. `ArmorDef` defines base AC, DEX cap, armor category (light/medium/heavy). `ShieldDef` defines AC bonus. `AccessoryDef` defines slot (HEAD/FEET/RING) and `grant_modifiers` (stat modifiers while equipped). `EquipmentSlot` enum: WEAPON, ARMOR, SHIELD, HEAD, FEET, RING. `rules/weapons.py`: `get_weapon_attack()` builds `Attack` from equipped weapon or falls back to creature attacks / unarmed strike. `rules/proficiency.py`: weapon/armor proficiency per class, proficiency bonus by level. Generic slot-based equip/unequip handlers in `rules/handlers/equipment.py` — `SlotConfig` maps each slot to item type, creature field, and action types. Item catalogs (`content/catalogs/items/`) define SRD weapons, armor, shield, and accessories as reusable YAML entries with an SRD `price`, resolved via `ref:` in entity definitions.

### Class Features & Resources

Composition-based class mechanics (`core/class_features.py`). Each D&D class gets a frozen dataclass (`FighterFeatures`, `RogueFeatures`, `PaladinFeatures`) with its own `collect_self_modifiers()` and `collect_attack_modifiers(melee=)` — classes declare their own modifiers; `rules/modifiers.py` iterates `creature.class_features` without knowing concrete types. `Character.class_features: list[ClassFeatures]` — multiclass gets multiple entries. `get_feature(FeatureType)` retrieves by type. Covers Fighting Styles (Defense +1 AC, Dueling +2 damage, GWF reroll), Sneak Attack dice, Cunning Action cost overrides (Dash/Disengage as bonus action), Divine Smite (`rules/divine_smite.py`).

Resource pools (`core/resource.py`) — `ResourcePool(id, max_uses, current_uses, reset_on)` on `Creature.resource_pools`. `RestType` (SHORT_REST, LONG_REST) controls when pools reset. Used for Second Wind (1/short rest), Paladin Lay on Hands (LONG_REST), Paladin spell slots (Level 1). Pure functions in `rules/resources.py`.

Action definitions (`core/action_defs.py`) — centralized `ActionDef` registry: cost, params, combat mode, flags, `TargetMode` (NONE/SELF/SINGLE) and `TargetScope` (HOSTILE/ALLY/ANY) per `ActionType`. `CostOverride` allows class features to change action costs (e.g. Cunning Action makes Dash a bonus action). Target scope is enforced in `rules/validation.py` with an explicit exception: HOSTILE-scope attacks outside active combat skip the faction check so the attack handler can auto-start combat via `forced_opponents`.

### XP & Leveling

`rules/leveling.py` — pure functions: `xp_for_cr(cr)` (D&D 5e MM table), `level_for_xp(xp)` / `xp_to_next_level(xp)` (PHB thresholds), `can_level_up(xp, level)`. On kill, the combat manager grants XP to `Character` attackers (`Creature.xp_value` on target, zero on other Characters), emits an `xp_gained` event, and updates `Character.level_up_available`. `perform_level_up(character, fighting_style=None)` (in `rules/perform_level_up.py`) applies class-specific L2 deltas: `FighterFeatures` → Action Surge pool, `RogueFeatures` → HP bump only, `PaladinFeatures` → Fighting Style + Divine Smite + level-1 spell slots. The operation is stateful (mutates the character in-place) and is invoked only through `GameService.level_up_player` / `GameService.player_status` — adapters never call the rule directly. Level gates class features: `collect_self_modifiers` / `collect_attack_modifiers` check `level >= required_level`, so a L1 Paladin cannot use Fighting Style or Smite.

### Modifier Pipeline

Centralized derived stat computation (`core/modifiers.py` data types, `rules/modifiers.py` pure functions). Modifiers represent effects on creature stats from conditions, equipment, spells, and class features. Each modifier has a `StatType` (AC, speed, attack_roll, initiative), a `ModifierOp` (ADD, OVERRIDE, ADVANTAGE, DISADVANTAGE), and an optional source (same source doesn't stack per D&D 5e). The pipeline collects modifiers from all sources via `collect_self_modifiers()` / `collect_defense_modifiers()`, then computes effective values: `effective_speed()`, `effective_ac()`, `attack_modifiers()`. Replaces ad-hoc stat computation that was scattered across combat_manager and conditions.

### Activation & Fast-Forward

Anchor-based activation: `EntitiesLayer.update_activation(time)` runs at the start of each round. Any living creature with `is_anchor=True` and no current intent holds its scene active; creatures at an anchor's location become active, all others go dormant. Content may additionally declare paired typed event triggers `{on, until}`: the indexed runtime activates a creature when `on` matches and removes that trigger reason when `until` matches; persistent GM overrides can force active or dormant. Creatures in combat stay active regardless. Wait, sleep, and travel are typed, persisted `current_intent` values. When no creature needs a turn, `Round.run_loop()` fast-forwards to the nearest timer or travel-leg boundary. Travel follows deterministic shortest paths one graph edge at a time and can be interrupted by damage, combat, or an occupied scene. Content requires explicit locations. On entering a location with an encounter table, `ActivationManager` rolls encounters (see Lairs, Encounters & Loot).

### Lairs, Encounters & Loot

**Lairs** (`core/lair.py`, hosted on `EcologyLayer`) — a fixed-roster monster population at a location with a `LairState` machine (`ACTIVE → DEPLETED`). While `ACTIVE`, population respawns to the roster cap on the ecology tick (interval `respawn_interval`); killing the optional `core`/boss depletes the lair permanently (terminal `DEPLETED`, respawn off, survives save/load). Lairs without a core can use an optional `depletion_chance` rolled after a full wipe. The full roster materializes when the player enters (reuses the squad materialization pattern; lair spawns are `temporary=True` and removed on death — no corpse loot).

**Encounters** — encounter tables are keyed by location (`encounters`) or region (`region_encounters`) in `ecology/monsters.yaml`; a location without its own table falls through to its region's table, a location table overrides. Resolution is load-time (`_flatten_region_defaults`, shared with `battle_map_configs`), so `ActivationManager` sees only effective per-location tables. Entries can carry a `time_of_day` tag (`TimeOfDay.DAY`/`NIGHT`); `ActivationManager._roll_encounters` filters via pure `rules/encounters.is_active_at_time`, reading day/night from the geography `IS_DAYLIGHT` query (resolves location→region→latitude→`is_daylight`); untagged entries fire at any time. Danger is fixed by place and time, never scaled to party level (kenshi-style, per VISION).

**Loot** — `InventoryHolder` Protocol (`core/loot.py`, anything with `inventory` + `gold`) with derived `is_lootable()` (dead creature or open container). The `take` action (`ActionType.TAKE`, `LootActionProvider`, handler in `rules/handlers/loot.py`) is take-all: one action transfers a holder's whole inventory + gold to the actor via the shared `rules/inventory.transfer_items` primitive (trade is refactored onto the same primitive; loot/trade/theft are separate access modes over it). Lair treasuries are persistent `Container` entities gated behind core death.

### Faction Relations, Reputation & Combat Sides

`faction_id` on Creature = origin (immutable). `reputation: dict[str, int]` = sparse personal reputation per-faction (default from faction-to-faction relations). `effective_relation(A, B)` (`rules/reputation.py`) — single source of truth: personal rep if set → thresholds (75+ FRIENDLY, 25-74 NEUTRAL, <25 HOSTILE), else same faction → FRIENDLY, else faction-to-faction fallback. `FactionRelation` enum (HOSTILE/NEUTRAL/FRIENDLY) in `core/models.py`.

`CombatSides` (`rules/combat_sides.py`) — `build_combat_sides(creatures, get_relation, forced_opponents)` assigns creatures to sides at combat start. Greedy: creatures join a side only if mutually FRIENDLY with all members, skip sides with forced opponents. Factionless creatures each get their own side. `forced_opponents` set from attack handler ensures attacker and target are always on different sides regardless of faction relations. Sides frozen for the duration of combat.

Kill reputation drop (`rules/reputation.py`): omniscient, delta scaled by victim's reputation with their own faction (killing an outcast ≈ 0 drop). Auto-hostility: attacking NPC outside combat starts combat with correct sides via `forced_opponents`.

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
- `DND_WORLD_SEED` env var seeds world simulation layers; when absent, `GameService` logs the generated seed.
- `DND_AUTOSAVE_SECONDS` env var controls periodic autosave interval (default: `120`; must be greater than `0`).
- `DND_ROUND_STOP_TIMEOUT_SECONDS` bounds round-thread shutdown before load/eviction aborts safely (default: `5`).
- Save files: `saves/` directory (JSON)
- Backend API: `make serve` → http://localhost:8001/docs (Swagger UI)
- Frontend: `make frontend` → http://localhost:5173 (entry point, proxies /api to :8001)
- GM inner-self API: `GET /api/master/sessions/{session_id}/creatures/{entity_id}/inner-self` returns the complete
  typed core and read-only personal layer. `PUT .../inner-self/core` completely replaces only `relations`, `mood`, and
  `goals`; its candidate is validated by the domain model and assigned once under the session world-state gate. Goal
  payloads explicitly discriminate `kind: typed` and `kind: freeform`; mood, relationship type, goal type and status
  are OpenAPI enums. Temporary creatures are not inner-self API bearers.
- Real-model smoke: export `OPENROUTER_API_KEY` and `LLM_MODEL` in both the server shell and the scenario shell. Start
  the server as `LOG_LEVEL=DEBUG LOG_DIR=./logs make serve`, then run `DND_LIVE_LOG=./logs make live-inner-self`.
  `DND_LIVE_LOG` is the server `LOG_DIR` directory, not a glob or an individual mirrored log file. The scenario creates
  and deletes its own session, keeps its player WebSocket open through the final snapshot, and prints core snapshots
  before combat, after combat and after the anchor departure boundary. It exits 2 with `SKIPPED / NOT RUNNABLE` if the
  credentials or server are absent; it exits 1 if the scenario does not complete and 0 if it completes. `WARN` lines
  can still appear with exit 0, so read the report checks as well.

  `PASS` confirms a measured prerequisite, such as a completed scenario, an observed digest boundary, an accepted LLM
  digest, or a retry that actually occurred. `INFO` describes non-failing model behaviour: a rules fallback, no thought,
  no core/journal rewrite, or no retry can all be legitimate. `WARN` means the PO acceptance did not establish a
  required condition: in particular, the scenario did not finish, no digest reached a boundary, or no LLM digest was
  accepted. The report reads only the current session's `full.jsonl`, so its counts exclude mirrored streams and earlier
  sessions.
