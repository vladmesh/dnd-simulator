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
├── core/          — foundation types, abstract Layer, World container, CombatState
├── layers/        — concrete layer implementations
│   ├── geography/ — physical world simulation
│   ├── politics/  — factions and diplomacy
│   ├── settlements/ — towns and local economy
│   └── entities/  — all tracked creatures (player, NPCs, named monsters)
├── master/        — DM orchestrator (LLM-powered)
├── rules/         — pure functions: D&D mechanics, combat/initiative resolution, movement/pathfinding, physics, economics
├── llm/           — LLM client (with logging), prompt builders (peaceful + combat), tool schemas (peaceful + combat)
├── adapters/      — transport layer (CLI, API, Telegram)
├── content_loader.py — loads worlds, nations, settlements, NPCs, player from YAML
├── service.py     — GameService: transport-agnostic game interface
└── game_loop.py   — turn-based main loop: polls active creatures, advances time each round

content/           — authored game data (YAML/JSON)
├── worlds/        — pre-built region maps
├── npcs/          — hand-crafted NPCs with backstories
├── quests/        — quest lines and storylines
└── triggers/      — event triggers (enter city → scene starts)
```

## Data Flow

```
Turn-based game loop (game_loop.py):
    for each active combat region (initiative order):
        for each combatant in turn_order:
            creature.take_turn(world)  → combat awareness → decide action → execute
        end_combat_round()            → 2 rounds without attacks → combat ends
    for each peaceful creature (not in combat):
        creature.take_turn(world)     → full awareness → decide action → execute
    world.advance_time(+1 round = 6 seconds)

Player input flow (service.py, command-based):
    Player input → Adapter (CLI/API/TG) → GameService → response
```

The game loop separates combat and peaceful turns. Combat regions use initiative order (d20 + DEX mod, rolled once at combat start); peaceful creatures use default order. Each creature builds awareness appropriate to its mode — combat awareness (HP, nearby combatants, round number) or full world awareness (time, weather, settlements). NPCs decide via LLM tool use, player via CLI input. Actions execute through world events. `World.advance_time()` checks each layer in order (0 → N) and only ticks those whose `tick_interval` has elapsed since their last tick. This way a 6-second combat round doesn't trigger monthly political updates. Events generated during ticks are propagated to all other layers.

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
└── Creature (ability_scores, HP, AC, in_combat, is_dodging)
    └── Character (race, class, alignment, gold, appearance, perceive_by_id)
        ├── PlayerCharacter (save/load, peaceful/combat turn modes)
        └── Npc (personality, schedule, conversation memory, LLM combat/peaceful tools)
```

All tracked entities live on the `EntitiesLayer`. Each entity has an `active` flag — only active entities are ticked. `Entity.on_tick(hour)` is a no-op by default; `Npc` overrides it to update activity based on daily schedule.

`Character.perceive(target: Entity) -> str` — observer extracts visible traits from target (race, appearance, wounds). LLM never receives raw character data, only what the observer can perceive.

## Combat System

Combat is managed by `EntitiesLayer` through `CombatState` and `BattleMap` (defined in `core/combat.py`). No separate combat layer — it's a mode within entities.

**Entry:** First attack in a region → `roll_initiative()` for all active creatures → `CombatState` created → all creatures in region get `in_combat=True`.

**Turn order:** Initiative = d20 + DEX modifier, tiebreaker by DEX score. Order is fixed for the entire combat. Game loop iterates combatants in this order.

**Battle map:** Each `CombatState` owns a `BattleMap` — a 2D grid (coordinates in feet, 5-ft cells). Entities have `Position`s on the map. `Wall` segments block movement between adjacent cells. Perimeter walls auto-generated from map dimensions. Movement uses `rules/movement.py`: D&D 5e alternating diagonal cost (5/10/5/…), wall collision, move-toward/away/direction helpers.

**Dual awareness:** Creatures in combat get a focused prompt (HP, weapon, nearby combatants with positions/distances, round number — no weather/time/politics). Peaceful creatures get full world awareness. Two separate tool sets: combat (attack/move/dodge/flee/idle, no say — use description for flavor) and peaceful (say/attack/idle).

**Dodge:** Creatures can use the dodge action (`is_dodging` flag on `Creature`). Attackers have disadvantage against dodging targets. The flag resets at the start of the creature's next turn.

**Exit conditions:**
- 2 consecutive rounds without any attack → auto-end
- Flee removes creature from turn order; if ≤1 left → end
- Death removes from turn order; if ≤1 left → end

**Events:** `COMBAT_STARTED` and `COMBAT_ENDED` are logged and perceived by all creatures in the region. Attack events include entity IDs so LLM can unambiguously identify participants.

## Key Principles

- **Layers depend down, never up.** Geography knows nothing about NPCs.
- **Rules are pure functions.** No state, no side effects, easy to test.
- **LLM is injected, not hardcoded.** Layers and Master receive an LLM client; they don't create one.
- **Content is data, not code.** Quests, NPCs, and world maps live in YAML files outside the Python package.
- **Transport is a thin adapter.** The game works the same whether accessed via terminal, HTTP, or Telegram.
