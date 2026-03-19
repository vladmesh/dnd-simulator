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
Layer 3: NPCs         — individual characters as LLM agents
```

New layers can be inserted between existing ones as the simulation grows in detail (e.g., a Cosmology layer above Geography for gods and planar mechanics).

Every layer implements the same interface:
- `tick(delta, world_state)` — advance simulation, return events
- `handle_event(event)` — react to something that happened
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
│   └── npcs/      — individual NPC agents
├── master/        — DM orchestrator (LLM-powered)
├── rules/         — pure functions: D&D mechanics, physics, economics
├── llm/           — LLM client abstraction and model configs
├── adapters/      — transport layer (CLI, API, Telegram)
└── service.py     — GameService: transport-agnostic game interface

content/           — authored game data (YAML/JSON)
├── worlds/        — pre-built region maps
├── npcs/          — hand-crafted NPCs with backstories
├── quests/        — quest lines and storylines
└── triggers/      — event triggers (enter city → scene starts)
```

## Data Flow

```
Player input
    → Adapter (CLI/API/TG)
    → GameService
    → Master (LLM)
        ↔ queries/events to Layers
        ↔ rules for dice rolls, formulas
    → GameService
    → Adapter
Player sees response
```

The Master decides when to advance time. When it does, `World.advance_time()` ticks all layers in order (0 → N), so each layer sees the already-updated state of layers below it. Events generated during ticks are propagated to all other layers.

## Key Principles

- **Layers depend down, never up.** Geography knows nothing about NPCs.
- **Rules are pure functions.** No state, no side effects, easy to test.
- **LLM is injected, not hardcoded.** Layers and Master receive an LLM client; they don't create one.
- **Content is data, not code.** Quests, NPCs, and world maps live in YAML files outside the Python package.
- **Transport is a thin adapter.** The game works the same whether accessed via terminal, HTTP, or Telegram.
