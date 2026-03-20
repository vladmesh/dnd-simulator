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
- `tick(delta, world_state)` — advance simulation, return events
- `handle_event(event) -> ActionResult` — process an event, return success/error and cascade events
- `query(question)` — answer a question about current state
- `get_state() / load_state()` — serialize/deserialize for saves

## Module Map

```
src/dnd_simulator/
├── core/          — foundation types, abstract Layer, World container
├── layers/        — concrete layer implementations
│   ├── geography/ — physical world simulation
│   ├── politics/  — factions and diplomacy
│   ├── settlements/ — towns and local economy
│   └── entities/  — all tracked creatures (player, NPCs, named monsters)
├── master/        — DM orchestrator (LLM-powered)
├── rules/         — pure functions: D&D mechanics, combat resolution, physics, economics
├── llm/           — LLM client (with request/response logging), prompt builders, tool schemas for NPC actions
├── adapters/      — transport layer (CLI, API, Telegram)
├── content_loader.py — loads worlds, nations, settlements, NPCs, player from YAML
├── service.py     — GameService: transport-agnostic game interface
└── game_loop.py   — turn-based main loop: polls active creatures in order

content/           — authored game data (YAML/JSON)
├── worlds/        — pre-built region maps
├── npcs/          — hand-crafted NPCs with backstories
├── quests/        — quest lines and storylines
└── triggers/      — event triggers (enter city → scene starts)
```

## Data Flow

```
Turn-based game loop (game_loop.py):
    for each active creature:
        creature.take_turn(world)  → perceive events → decide action (LLM/player input) → execute

Player input flow (service.py, command-based):
    Player input → Adapter (CLI/API/TG) → GameService → response
```

The game loop polls all active creatures in turn order. Each creature builds its own awareness from perceived events, decides an action (NPCs via LLM tool use, player via CLI input), and executes it through world events. `World.advance_time()` checks each layer in order (0 → N) and only ticks those whose `tick_interval` has elapsed since their last tick. This way a 6-second combat round doesn't trigger monthly political updates. Events generated during ticks are propagated to all other layers.

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
Entity (id, name, region_id, active, on_tick)
└── Creature (ability_scores, HP, AC)
    └── Character (race, class, alignment, gold, appearance)
        ├── PlayerCharacter (save/load mutable state)
        └── Npc (personality, schedule, conversation memory)
```

All tracked entities live on the `EntitiesLayer`. Each entity has an `active` flag — only active entities are ticked. `Entity.on_tick(hour)` is a no-op by default; `Npc` overrides it to update activity based on daily schedule.

`Character.perceive(target: Entity) -> str` — observer extracts visible traits from target (race, appearance, wounds). LLM never receives raw character data, only what the observer can perceive.

## Key Principles

- **Layers depend down, never up.** Geography knows nothing about NPCs.
- **Rules are pure functions.** No state, no side effects, easy to test.
- **LLM is injected, not hardcoded.** Layers and Master receive an LLM client; they don't create one.
- **Content is data, not code.** Quests, NPCs, and world maps live in YAML files outside the Python package.
- **Transport is a thin adapter.** The game works the same whether accessed via terminal, HTTP, or Telegram.
