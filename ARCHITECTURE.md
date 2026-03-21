# Architecture

## Overview

The simulator is built as a stack of simulation layers, each depending only on the layers below it. A World container manages global time and propagates events between layers. An LLM-powered Master (Dungeon Master) orchestrates everything — interpreting player actions, querying layers, advancing time, and composing narrative responses.

The game logic is fully transport-agnostic: a `GameService` provides the interface, and thin adapters (CLI, REST API, Telegram) plug into it.

## Layer Stack

Layers are ordered from most abstract (physical world) to most concrete (individuals). Each layer can read state from layers below, but never above.

```
Layer 0: Geography    — terrain, coordinates, weather, day/night cycle
Layer 1: Politics     — factions, borders, laws, diplomacy
Layer 2: Settlements  — towns, economy, population, local events
Layer 3: Entities     — all tracked creatures (player, NPCs, named monsters)
```

New layers can be inserted between existing ones as the simulation grows in detail (e.g., a Cosmology layer above Geography for gods and planar mechanics).

Every layer implements the same interface:
- `tick_interval` — minimum seconds between ticks (0 = every call)
- `tick(delta, time, query_fn, emit_fn)` — advance simulation, return events
- `handle_event(event, query_fn, emit_fn) -> ActionResult` — process an event, return success/error and cascade events
- `query(question)` — answer a question about current state

`query_fn` and `emit_fn` are injected by World at call time. `query_fn` enforces layer ordering — a layer can only query layers below it (by index). `emit_fn` sends events back to World for propagation with source validation.
- `get_state() / load_state()` — serialize/deserialize for saves

## Module Map

```
src/dnd_simulator/
├── core/          — foundation types, abstract Layer, World container, CombatState, Brain/Action, LocationGraph
├── layers/        — concrete layer implementations
│   ├── geography/ — physical world simulation
│   ├── politics/  — factions and diplomacy
│   ├── settlements/ — towns and local economy
│   └── entities/  — all tracked creatures (player, NPCs, named monsters)
├── master/        — DM orchestrator (LLM-powered)
├── rules/         — pure functions: D&D mechanics, combat/initiative resolution, movement/pathfinding, physics, economics
├── llm/           — LLM client (with logging), LlmBrain, prompt builders (peaceful + combat), tool schemas, MemorySummarizer
├── i18n.py        — gettext internationalization, per-session language via contextvars
├── adapters/      — transport layer
│   ├── cli.py, cli_loop.py — terminal REPL
│   └── api/       — FastAPI REST adapter (master + player routes, i18n middleware)
├── content_loader.py — loads content from YAML (single file or directory format)
├── content_saver.py  — saves world templates back to YAML
├── service/       — GameService + command modules
│   ├── game_service.py — session management, command routing, hot controls
│   ├── session.py      — GameSession: world + player state, autosave
│   ├── commands_combat.py, commands_npc.py, commands_politics.py, ...
│   └── commands_save.py, commands_time.py, commands_world.py
└── round.py       — Round orchestrator: multi-action turn loop with budget enforcement

content/           — authored game data (YAML)
└── worlds/        — world templates (single .yaml file or directory with split files)
    ├── arena.yaml          — single-file format (combat arena)
    ├── village.yaml        — single-file format (village scenario)
    └── sword_vale/         — directory format (world.yaml, regions.yaml, nations.yaml, npcs.yaml, locations.yaml)
```

## Data Flow

```
Round orchestrator (round.py):
    for each active combat location (initiative order):
        for each combatant in turn_order:
            run_creature_turn:
                build TurnBudget from creature stats
                loop:
                    build_awareness → brain.choose_action → action_cost check
                    → execute_action → on_action callback → repeat
                    until end_turn or budget exhausted
        end_combat_round()            → 2 rounds without attacks → combat ends
    for each peaceful creature (not in combat):
        run_creature_turn (same multi-action loop)
    world.advance_time(+1 round = 6 seconds)

Player input flow (service/, command-based):
    Player input → Adapter (CLI/API/TG) → GameService → response

REST API flow (adapters/api/):
    FastAPI routes → GameService methods → JSON responses
    I18nMiddleware sets session language before each request via contextvars
    Master routes: session CRUD, NPC hot controls, nation/settlement patching, saves
    Player routes: character creation, perception, events, combat, map, actions
```

The `Round` class separates combat and peaceful turns. Combat locations use initiative order (d20 + DEX mod, rolled once at combat start); peaceful creatures use default order. Each creature's turn is a multi-action loop: a `TurnBudget` is created from creature stats, then the brain is called repeatedly until it returns `end_turn` or the budget is exhausted. `action_cost()` (in `rules/actions.py`) maps each action to its cost (standard action, bonus action, or movement feet). Brains receive structured awareness (`PeacefulAwareness` or `CombatAwareness` from `core/awareness.py`) with the current budget attached, so they can make informed decisions. Three brain types: `RuleBrain` (utility scoring), `LlmBrain` (LLM calls), `PlayerBrain` (queue + on_turn callback for interactive I/O). `World.advance_time()` checks each layer in order (0 → N) and only ticks those whose `tick_interval` has elapsed since their last tick. This way a 6-second combat round doesn't trigger monthly political updates. Events generated during ticks are propagated to all other layers.

`World.handle_event()` sends an event to all layers in order. Each layer returns an `ActionResult` — if any layer returns `success=False`, propagation stops and the failure is returned to the caller. This lets layers validate and reject actions (e.g., EntitiesLayer rejects attacks on dead targets).

Events carry an optional `observer_ids` field (`frozenset[str] | None`). When `None`, the event is public — visible to all entities in the area. When set, only listed entity IDs can perceive the event. The `perception` module in `layers/entities/` converts raw events into subjective text through `observer.perceive()`, so the same event reads differently to different characters.

## Time System

Game time is tracked with second precision via `GameDateTime` (year/month/day/hour/minute/second). Time advances in `TimeDelta` increments measured in seconds, with convenience factories: `TimeDelta.from_rounds(n)` (1 round = 6 seconds, D&D standard), `TimeDelta.from_hours(n)`, `TimeDelta.from_days(n)`.

Each layer declares a `tick_interval` in seconds. World tracks `_last_tick_time` per layer and only calls `tick()` when enough time has elapsed:
- Geography, Entities: `tick_interval = 0` (every advance_time call)
- Settlements, Politics: `tick_interval = 2 592 000` (30 days)

Calendar: 30 days/month, 12 months/year.

## Entity Hierarchy

```
Entity (id, name, location_id, active, on_tick)
└── Creature (ability_scores, HP, AC, in_combat, is_dodging, brain, execute_action)
    └── Character (race, class, alignment, gold, appearance, perceive_by_id, get_npc_data)
        ├── PlayerCharacter (interactive I/O, overrides take_turn directly)
        └── Npc (role, personality, schedule, memory: NpcMemory, ai_type — brain assigned by content_loader/adapter)
```

All tracked entities live on the `EntitiesLayer`. Each entity has an `active` flag — only active entities are ticked. `Entity.on_tick(hour)` is a no-op by default; `Npc` overrides it to update activity based on daily schedule.

`World.location_graph` (`LocationGraph`) provides a flat graph of all locations. Each `Location` node has a `region_id` tag (for weather/terrain lookups) and an optional `settlement_id` tag (for economy/NPC binding). Entities hold a `location_id` and the graph resolves which region/settlement they are in. Edges between locations carry distances in meters; `travel_seconds()` computes travel time.

### NPC Memory

NPCs carry structured memory via `NpcMemory` (tags, recent, inner_state, current_conversation). Tags use `NpcTag` vocabulary — emotions (`angry`, `scared`) and relations (`hates:orc_chief`, `fears:player`). Tags are readable by both `RuleBrain` (direct checks for target selection, flee thresholds, mood-based canned dialogue) and `LlmBrain` (included in prompt context). A `MemorySummarizer` (in `llm/summarizer.py`) compresses NPC event logs into memory via a cheap LLM call, triggered after combat ends or when the `recent` field overflows 300 characters. Memory can be pre-loaded from YAML content files.

`Character.perceive(target: Entity) -> str` — observer extracts visible traits from target (race, appearance, wounds). LLM never receives raw character data, only what the observer can perceive.

## Combat System

Combat is managed by `EntitiesLayer` through `CombatState` and `BattleMap` (defined in `core/combat.py`). No separate combat layer — it's a mode within entities.

**Entry:** First attack in a location → `roll_initiative()` for all active creatures → `CombatState` created → all creatures in location get `in_combat=True`.

**Turn order:** Initiative = d20 + DEX modifier, tiebreaker by DEX score. Order is fixed for the entire combat. Game loop iterates combatants in this order.

**Battle map:** Each `CombatState` owns a `BattleMap` — a 2D grid (coordinates in feet, 5-ft cells). Entities have `Position`s on the map. `Wall` segments block movement between adjacent cells. Perimeter walls auto-generated from map dimensions. Movement uses `rules/movement.py`: D&D 5e alternating diagonal cost (5/10/5/…), wall collision, move-toward/away/direction helpers.

**Dual awareness:** Creatures in combat get a focused prompt (HP, weapon, nearby combatants with positions/distances, round number — no weather/time/politics). Peaceful creatures get full world awareness. Two separate tool sets: combat (attack/move/dodge/flee/idle, no say — use description for flavor) and peaceful (say/attack/idle).

**Dodge:** Creatures can use the dodge action (`is_dodging` flag on `Creature`). Attackers have disadvantage against dodging targets. The flag resets at the start of the creature's next turn.

**Exit conditions:**
- 2 consecutive rounds without any attack → auto-end
- Flee removes creature from turn order; if ≤1 left → end
- Death removes from turn order; if ≤1 left → end

**Events:** `COMBAT_STARTED` and `COMBAT_ENDED` are logged and perceived by all creatures in the location. Attack events include entity IDs so LLM can unambiguously identify participants.

## Key Principles

- **Layers depend down, never up.** Geography knows nothing about NPCs. Enforced at runtime via `query_fn`/`emit_fn` callbacks injected by World — layers can only query layers below them by index.
- **Rules are pure functions.** No state, no side effects, easy to test.
- **Brain is a strategy.** `Creature.brain` decouples decision-making from entity type. `RuleBrain` (utility scoring + canned dialogue) needs no LLM; `LlmBrain` wraps an `LlmClient`; `PlayerBrain` uses queue + callback for interactive input. Brains are swappable at runtime (LOD).
- **LLM is injected, not hardcoded.** `LlmBrain` receives an `LlmClient`; rule-based NPCs use no LLM at all.
- **Content is data, not code.** Worlds and NPCs live in YAML files. Two formats: legacy single file, or directory (world.yaml, regions.yaml, nations.yaml, npcs.yaml, locations.yaml). ContentLoader handles both.
- **Transport is a thin adapter.** The game works the same whether accessed via terminal, HTTP, or Telegram. REST API (FastAPI) is the primary adapter for frontend.
- **Two editing modes.** Between sessions: master edits YAML templates on disk. During sessions: hot controls (NPC spawn/delete, HP, brain, nation/settlement patches) modify objects in memory. Saves persist state to disk.
- **Per-session i18n.** Language is set per session via `contextvars`. The global `_()` function reads the current context, so NPC LLM prompts and translated strings respect session language.
