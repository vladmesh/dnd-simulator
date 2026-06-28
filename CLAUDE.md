# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install      # uv sync — install all dependencies
make check        # backend + frontend lint/typecheck/test (mirrors CI minus integration)
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

## Product Vision

See [docs/VISION.md](docs/VISION.md) for product vision and [docs/ROADMAP.md](docs/ROADMAP.md) for current status and plans.

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
layers/            — concrete layer implementations (depend on core only)
  ↓
round.py           — Round orchestrator: multi-action turn loop with budget enforcement
service/           — GameService, ActionDispatcher, BrainFactory, command modules
  ↓
adapters/          — FastAPI REST + WebSocket API

rules/             — pure D&D mechanics: combat, validation, conditions, weapons, modifiers, proficiency, sneak attack, divine smite, fighting style, resources, character creation (point buy, HP, starting equipment), leveling (XP-by-CR, thresholds, perform_level_up), action providers, handlers/ package, reputation, combat_sides, encounters (time-of-day gate), inventory (transfer_items), loot, rule_brain (no deps)
llm/               — LLM client, prompt builders, tool schemas (OpenRouter)
storage/           — SaveStore interface, JsonFileStore
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

`Entity` (id, name, location_id, active, on_tick) → `Creature` (ability scores, HP, AC, speed, attacks, conditions, inventory, gold, in_combat, is_dodging, is_disengaging, wake_at_seconds, brain, turn_budget, combat_position, equipped_weapon, equipped_armor, equipped_shield, equipped_head, equipped_feet, equipped_ring, resource_pools, faction_id, reputation, xp_value) → `Character` (race, class, alignment, class_features, level, experience, level_up_available) → `PlayerCharacter` / `Npc`. Creature delegates decisions to `brain.choose_action()`. `Container` (`core/container.py`) is a separate `Entity` sibling of `Creature` — inventory + gold, no HP/turn/brain — used for lair treasuries and other lootable world objects (`EntityKind.CONTAINER`). The `perceive()` method controls what information an observer sees about a target — LLM prompts never receive raw character data. All tracked entities live on the `EntitiesLayer`. `World.location_graph` (`LocationGraph`) maps locations to regions/settlements; entities reference `location_id`, and the graph resolves which region/settlement a location belongs to. NPCs have structured memory (`NpcMemory`: tags, recent, inner_state, current_conversation) readable by both LLM and RuleBrain; a `MemorySummarizer` compresses events into memory via LLM after combat/conversation ends. Combat is managed via `CombatState` (initiative order, round tracking, combat sides, auto-exit after 2 idle rounds) and `BattleMap` (2D grid with positions, walls, and movement). Movement rules live in `rules/movement.py` (D&D 5e diagonal distance, wall collision, occupied-cell blocking). `move_to(x, y)` action uses BFS pathfinding (`find_path`) and budget-aware stepping (`step_cost`); player-only (frontend click-to-move), excluded from LLM action schemas via `provider_managed=True`.

### Multi-Action Turns

Each creature's turn is a multi-action loop orchestrated by `Round` (in `round.py`). A `TurnBudget` (actions, bonus_actions, movement_remaining, reaction) lives on `Creature.turn_budget` — persists between turns for reaction spending. Created fresh at the start of each creature's turn. The brain is called repeatedly: choose action → `ActionDispatcher` validates (budget, target, reach via `rules/validation.py`) → executes handler (`rules/handlers/`) → rebuilds awareness → repeat, until the brain returns `end_turn` or budget is exhausted. `ActionProvider` (`rules/action_provider.py`) determines which actions are currently available to a creature. `PlayerBrain` uses a queue + callback pattern for interactive I/O.

### Reactions & Opportunity Attacks

D&D 5e reaction system. `Brain.choose_reaction(creature, trigger, available_reactions)` — unified method on ABC (RuleBrain: always attack, LlmBrain: LLM call, PlayerBrain: callback + queue). `ReactionTrigger` typed data object (extensible: `TriggerType.LEAVING_REACH` for OA, future: Counterspell, Shield). Movement handlers call `on_leave_reach` callback (injected via `ActionContext`) when a mover exits an enemy's reach. `check_reactions` in Round is recursive — a reaction can trigger another reaction, depth limited naturally (1 reaction per creature per round). `rules/reactions.py`: pure function `find_oa_triggers()`. OA handler in `rules/handlers/reactions.py`. Disengage sets `creature.is_disengaging = True` (reset at turn start), prevents OA. `Creature.combat_position` enables deterministic battle map placement from YAML/API.

### Conditions & Items

D&D 5e conditions (`core/conditions.py`) — `Condition` enum + `ConditionsMap` (condition → remaining rounds or permanent). Pure mechanics in `rules/conditions.py`: `is_incapacitated()`, `effective_speed()`, `attack_advantage()`. Conditions tick down at turn start; weapons can grant permanent conditions while equipped.

Items (`core/items.py`) — `Item` with `ItemType` (WEAPON, POTION, ARMOR, SHIELD, ACCESSORY). `WeaponDef` defines attack name, damage, reach, ability, magic bonus, finesse, category, two-handed, light, heavy, and can grant conditions/actions. `ArmorDef` defines base AC, DEX cap, armor category (light/medium/heavy). `ShieldDef` defines AC bonus. `AccessoryDef` defines slot (HEAD/FEET/RING) and `grant_modifiers` (stat modifiers while equipped). `EquipmentSlot` enum: WEAPON, ARMOR, SHIELD, HEAD, FEET, RING. `rules/weapons.py`: `get_weapon_attack()` builds `Attack` from equipped weapon or falls back to creature attacks / unarmed strike. `rules/proficiency.py`: weapon/armor proficiency per class, proficiency bonus by level. Generic slot-based equip/unequip handlers in `rules/handlers/equipment.py` — `SlotConfig` maps each slot to item type, creature field, and action types. Item catalogs (`content/catalogs/items/`) define SRD weapons (12) and armor (12 + shield) as reusable YAML entries resolved via `ref:` in entity definitions.

### Class Features & Resources

Composition-based class mechanics (`core/class_features.py`). Each D&D class gets a frozen dataclass (`FighterFeatures`, `RogueFeatures`, `PaladinFeatures`) with its own `collect_self_modifiers()` and `collect_attack_modifiers(melee=)` — classes declare their own modifiers; `rules/modifiers.py` iterates `creature.class_features` without knowing concrete types. `Character.class_features: list[ClassFeatures]` — multiclass gets multiple entries. `get_feature(FeatureType)` retrieves by type. Covers Fighting Styles (Defense +1 AC, Dueling +2 damage, GWF reroll), Sneak Attack dice, Cunning Action cost overrides (Dash/Disengage as bonus action), Divine Smite (`rules/divine_smite.py`).

Resource pools (`core/resource.py`) — `ResourcePool(id, max_uses, current_uses, reset_on)` on `Creature.resource_pools`. `RestType` (SHORT_REST, LONG_REST) controls when pools reset. Used for Second Wind (1/short rest), Paladin Lay on Hands (LONG_REST), Paladin spell slots (Level 1). Pure functions in `rules/resources.py`.

Action definitions (`core/action_defs.py`) — centralized `ActionDef` registry: cost, params, combat mode, flags, `TargetMode` (NONE/SELF/SINGLE) and `TargetScope` (HOSTILE/ALLY/ANY) per `ActionType`. `CostOverride` allows class features to change action costs (e.g. Cunning Action makes Dash a bonus action). Target scope is enforced in `rules/validation.py` with an explicit exception: HOSTILE-scope attacks outside active combat skip the faction check so the attack handler can auto-start combat via `forced_opponents`.

### XP & Leveling

`rules/leveling.py` — pure functions: `xp_for_kill(cr)` (D&D 5e MM table), `level_for_xp(xp)` / `xp_to_next_level(xp)` (PHB thresholds), `can_level_up(xp, level)`. On kill, the combat manager grants XP to `Character` attackers (`Creature.xp_value` on target, zero on other Characters), emits an `xp_gained` event, and updates `Character.level_up_available`. `perform_level_up(character, fighting_style=None)` (in `rules/leveling.py`) applies class-specific L2 deltas: `FighterFeatures` → Action Surge pool, `RogueFeatures` → HP bump only, `PaladinFeatures` → Fighting Style + Divine Smite + level-1 spell slots. The operation is stateful (mutates the character in-place) and is invoked only through `GameService.level_up_player` / `GameService.player_status` — adapters never call the rule directly. Level gates class features: `collect_self_modifiers` / `collect_attack_modifiers` check `level >= required_level`, so a L1 Paladin cannot use Fighting Style or Smite.

### Modifier Pipeline

Centralized derived stat computation (`core/modifiers.py` data types, `rules/modifiers.py` pure functions). Modifiers represent effects on creature stats from conditions, equipment, spells, and class features. Each modifier has a `StatType` (AC, speed, attack_roll, initiative), a `ModifierOp` (ADD, OVERRIDE, ADVANTAGE, DISADVANTAGE), and an optional source (same source doesn't stack per D&D 5e). The pipeline collects modifiers from all sources via `collect_self_modifiers()` / `collect_defense_modifiers()`, then computes effective values: `effective_speed()`, `effective_ac()`, `attack_modifiers()`. Replaces ad-hoc stat computation that was scattered across combat_manager and conditions.

### Activation & Fast-Forward

Proximity-based activation: `EntitiesLayer.update_activation(time)` runs at the start of each round. Players without `wake_at_seconds` are anchors — creatures at an anchor's location become active, all others go dormant. Creatures in combat stay active regardless. `wait` action sets `creature.wake_at_seconds` and marks it dormant. When no active creatures exist, `Round.run_loop()` fast-forwards time to the nearest `wake_at`, then re-checks activation. Content requires explicit locations — no auto-generation from regions. On entering a location with an encounter table, `ActivationManager` rolls encounters (see Lairs, Encounters & Loot).

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
- Save files: `saves/` directory (JSON)
- Backend API: `make serve` → http://localhost:8001/docs (Swagger UI)
- Frontend: `make frontend` → http://localhost:5173 (entry point, proxies /api to :8001)
