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
Layer 3: Ecology      — squad movement, lairs, abstract world simulation
Layer 4: Entities     — all tracked creatures (player, NPCs, named monsters) + Container loot objects
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
├── core/          — foundation types, abstract Layer, World container, CombatState, Brain/BrainType/Action, CreatureHost protocol, LocationGraph, Condition, Item/WeaponDef/ArmorDef, Modifier, ClassFeatures, ResourcePool, ActionDef/TargetMode/TargetScope, EntityKind, NpcMemory, Squad, Lair/LairState, Container, InventoryHolder/Lootable, TimeOfDay
├── layers/        — concrete layer implementations
│   ├── geography/ — physical world simulation
│   ├── politics/  — factions and diplomacy
│   ├── settlements/ — towns and local economy
│   ├── ecology/   — squad movement, lairs, abstract world simulation (EcologyLayer)
│   └── entities/  — all tracked creatures (player, NPCs, named monsters)
│       ├── layer.py              — EntitiesLayer (main)
│       ├── combat_manager.py     — CombatManager (attack resolution, initiative)
│       ├── awareness_builder.py  — AwarenessBuilder (creature awareness construction)
│       ├── activation_manager.py — ActivationManager (proximity activation + encounter rolling, region/time-of-day)
│       ├── query_handler.py      — QueryHandler (layer query dispatch)
│       └── perception.py         — event perception and visibility filtering
├── master/        — DM orchestrator (LLM-powered)
├── rules/         — pure functions: D&D mechanics, combat/initiative, movement, validation (+ target scope), conditions, weapons, modifiers, proficiency, sneak attack, divine smite, fighting style, reactions, reputation, combat_sides, resources, character creation, leveling (XP/thresholds/perform_level_up), action providers, encounters (time-of-day gate), inventory (transfer_items), loot, abstract combat, physics, economics, RuleBrain (utility scoring)
│   └── handlers/  — per-action-type execution (combat, attack_resolution, movement, equipment, items, rest, trade, loot, reactions)
├── llm/           — LLM client (with logging), LlmBrain, prompt builders (peaceful + combat), tool schemas, MemorySummarizer (layer-agnostic: only depends on core/ and rules/)
├── i18n.py        — gettext internationalization, per-session language via contextvars
├── adapters/      — transport layer
│   └── api/       — FastAPI REST + WebSocket adapter
│                    routes_session.py (sessions, spawn, patch, time advance),
│                    routes_world.py (world/library, layers, fork/delete),
│                    routes_player.py (player actions, awareness),
│                    routes_content.py (CRUD + schemas),
│                    routes_ws.py (WebSocket loop),
│                    app.py / deps.py / schemas.py
│                    also serves React SPA build
├── content_loader/ — loads content from YAML directory format; locations must be explicit
│   ├── schemas.py    — Pydantic content models (RegionContent, NpcContent, etc.) — source of truth for validation
│   ├── schema_gen.py — JSON Schema generation from Pydantic models, enum injection, layer-refs resolution
│   ├── crud.py       — EntityRegistry: generic CRUD for world entities and catalog items (list/get/create/update/delete YAML)
│   ├── refs.py       — cross-layer reference resolution (locations → regions, NPCs → settlements)
│   ├── catalogs.py   — catalog loader: index standalone YAML files from content/catalogs/{monsters,items}/
│   ├── world.py      — world meta, regions, nations, settlements, locations, battle maps, factions
│   ├── creatures.py  — player, NPCs, ability scores, class features
│   ├── monsters.py   — monster templates, squads, encounters (supports catalog refs)
│   ├── items.py      — equipment parsing (weapons, armor, shields, supports catalog refs)
│   ├── manifest.py   — manifest.yaml resolution (LayerType, LayerSource, resolve layer paths)
│   ├── library.py    — library catalog (TemplateInfo, list/filter templates by compatibility)
│   ├── assembly.py   — world assembly (create manifest from library selections) and fork (copy to custom)
│   └── utils.py      — YAML section loading, text resolution
├── service/       — GameService + command modules
│   ├── game_service.py — session management, command routing, creature hot controls; composes the WorldBuilderCommands + PlayerCommands mixins
│   ├── commands_worldbuilder.py — WorldBuilderCommands mixin: world templates/manifest, layer files, entity/catalog CRUD
│   ├── commands_player.py  — PlayerCommands mixin: create_player, level_up_player, player_status
│   ├── session.py      — GameSession: world ref, player lookup via entities layer, autosave
│   ├── action_dispatcher.py — validate → route → execute (single entry point for all actions)
│   ├── action_parsing.py    — parse JSON action payloads into Action (ActionParseError); keeps adapters off core Action/ActionType
│   ├── brain_factory.py     — creates Brain instances from BrainType
│   ├── base.py              — GameServiceProtocol base shared by the command mixins
│   ├── dto.py               — typed DTOs returned by service methods (PlayerStatusData, ResourcePoolView)
│   └── commands_creatures.py, commands_politics.py, commands_save.py, commands_time.py, commands_world_state.py
└── round.py       — Round orchestrator: multi-action turn loop with budget enforcement

content/           — authored game data (YAML)
├── library/       — reusable layer templates (1 template = 1 layer type)
│   ├── geography/{slug}/  — metadata.yaml + regions.yaml, locations.yaml
│   ├── politics/{slug}/   — metadata.yaml + nations.yaml, factions.yaml
│   ├── settlements/{slug}/ — metadata.yaml + settlements.yaml
│   ├── ecology/{slug}/    — metadata.yaml + squads.yaml, monsters.yaml
│   └── entities/{slug}/   — metadata.yaml + npcs.yaml
└── worlds/        — assembled worlds (manifest.yaml + optional custom layer dirs)
    ├── sword_vale/         — multi-region world (all layers from library)
    └── test_vale/          — minimal test world (all custom layers)

frontend/          — React + TypeScript SPA (Vite + shadcn/ui + Zustand)
├── src/components/         — LandingPage (Player/DM split), ErrorBoundary
├── src/components/setup/   — world picker, character creation, session connect (player flow)
├── src/components/game/    — GameScreen (dashboard: 3-col grid), EventLog (compact strip + expand overlay),
│                             BattleMap (interactive CSS Grid, click-to-move, click-to-inspect),
│                             ActionBar (orchestrator) + action-bar/ (ActionButton, SayAction, drawers, utils),
│                             CombatPanel, NpcInspectModal, Perception, LocationPanel
├── src/components/master/  — MasterScreen (Worlds/Sessions tabs), WorldEditor (layer stepper),
│                             EntityListEditor (schema-driven CRUD), SchemaForm, CatalogBrowser,
│                             SessionView (WorldOverview, CreatureList, TimeControl, SavesPanel)
├── src/store/              — Zustand store (slices: connection, player, turn, log)
├── src/transport/          — apiClient (REST), wsClient (WebSocket)
└── src/i18n/               — i18next with EN/RU locale files
```

## Data Flow

```
Round orchestrator (round.py):
    update_activation(time)               → proximity-based active/dormant
    for each active combat location (initiative order):
        for each combatant in turn_order:
            run_creature_turn:
                build TurnBudget from creature stats
                loop:
                    build_awareness → brain.choose_action
                    → ActionDispatcher: validate (budget/target/reach) → handler → budget consume
                    → on_action callback → repeat
                    until end_turn or budget exhausted
        end_combat_round()            → 2 rounds without attacks → combat ends
    for each peaceful creature (not in combat):
        run_creature_turn (same multi-action loop)
    world.advance_time(+1 round = 6 seconds)

run_loop:
    while not stopped:
        update_activation → get active creatures
        if none active → fast_forward to nearest intent boundary or exit
        run_round → on_round_end callback

Player input flow (service/, command-based):
    Player input → Adapter (CLI/API/TG) → GameService → response

REST API flow (adapters/api/):
    FastAPI routes → GameService methods → JSON responses
    I18nMiddleware sets session language before each request via contextvars
    Master routes: session CRUD, creature hot controls, nation/settlement patching, saves
    Player routes: character creation, perception, events, combat, map, actions

WebSocket flow (React frontend):
    Frontend wsClient → WS /api/ws/{session_id} → routes_ws.py
    GameSession owns Round lifecycle (start/stop round thread)
    Round thread fires callbacks → SessionEventListener → WS messages → Zustand store
    Player actions: WS message → PlayerBrain queue → Round processes → broadcast result
```

`GameSession` (in `service/session.py`) owns the `Round` lifecycle — starting and stopping the round thread, bridging events to transport listeners via `SessionEventListener` protocol. The `Round` class separates combat and peaceful turns. Combat locations use initiative order (d20 + DEX mod, rolled once at combat start); peaceful creatures use default order. Each creature's turn is a multi-action loop: a `TurnBudget` is created from creature stats, then the brain is called repeatedly until it returns `end_turn` or the budget is exhausted. `ActionDispatcher` (`service/action_dispatcher.py`) is the single entry point: it validates preconditions via `rules/validation.py` (alive, budget, target validity, weapon reach), routes to the appropriate handler in `rules/handlers/`, and consumes budget on success. `ActionProvider` (`rules/action_provider.py`) determines available actions per creature based on state, inventory, and weapon. Brains receive structured awareness (`PeacefulAwareness` or `CombatAwareness` from `core/awareness.py`) with the current budget attached, so they can make informed decisions. Three brain types: `RuleBrain` (utility scoring), `LlmBrain` (LLM calls), `PlayerBrain` (queue + on_turn callback for interactive I/O). `World.advance_time()` checks each layer in order (0 → N) and only ticks those whose `tick_interval` has elapsed since their last tick. This way a 6-second combat round doesn't trigger monthly political updates. Events generated during ticks are propagated to all other layers.

`World.handle_event()` sends an event to all layers in order. Each layer returns an `ActionResult`; if any layer returns `success=False`, propagation stops and the failure is returned to the caller. This lets layers validate and reject actions (for example, EntitiesLayer rejects attacks on dead targets).

Each `EventType` has a fixed immutable payload class in `core/events.py`; `Event` validates the pairing at construction, and transport/log boundaries encode it to JSON-safe data. Events carry an optional `observer_ids` field (`frozenset[str] | None`). When `None`, the event is public; when set, only listed entity IDs can perceive it. The entities trigger index matches typed payload fields against YAML-defined paired `{on, until}` conditions, changing a creature's activation reason without scanning all creatures. The `perception` module converts visible events into subjective text through `observer.perceive()`.

## Time System

Game time is tracked with second precision via `GameDateTime` (year/month/day/hour/minute/second). Time advances in `TimeDelta` increments measured in seconds, with convenience factories: `TimeDelta.from_rounds(n)` (1 round = 6 seconds, D&D standard), `TimeDelta.from_hours(n)`, `TimeDelta.from_days(n)`.

Each layer declares a `tick_interval` in seconds. World tracks `_last_tick_time` per layer and only calls `tick()` when enough time has elapsed:
- Geography: `tick_interval = 0` (every advance_time call)
- Ecology: `tick_interval = 3600` (1 hour) — per-squad cooldowns for movement
- Entities: `tick_interval = 0` but `tick()` is a no-op — Round orchestrator drives all creature turns
- Settlements, Politics: `tick_interval = 2 592 000` (30 days)

Calendar: 30 days/month, 12 months/year.

## Entity Hierarchy

```
Entity (id, name, location_id, active, on_tick)
└── Creature (ability_scores, HP, AC, in_combat, is_dodging, is_disengaging, is_anchor, current_intent, brain, turn_budget, combat_position, equipment, resource_pools, faction_id, reputation, squad_id, xp_value, execute_action)
    └── Character (race, class, alignment, gold, appearance, class_features, level, experience, level_up_available, perceive_by_id, get_npc_data)
        ├── PlayerCharacter (interactive I/O, overrides take_turn directly)
        └── Npc (role, personality, schedule, memory: NpcMemory, ai_type — brain assigned by content_loader/adapter)
```

All tracked entities live on the `EntitiesLayer`. The layer's `tick()` is a no-op — the Round orchestrator calls `run_creature_turn` directly for both combat and peaceful turns. `Entity.on_tick(hour)` is called by the Round to update NPC activity based on daily schedule.

**Activation system:** `EntitiesLayer.update_activation(time)` runs at the start of each round. Any living creature with `is_anchor=True` and no `current_intent` holds its location active; creatures at an anchor's location become active, all others go dormant. Creatures in combat stay active. NPCs are moved to their scheduled location when activated. Wait and sleep use persisted `TimedIntent`; travel uses persisted `TravelIntent` with a destination, remaining route, and next edge-arrival boundary. `Round.run_loop()` fast-forwards to the nearest intent boundary when no creature needs a turn. Travel advances one graph edge per boundary and can be interrupted by damage, combat, or arrival in an occupied scene.

`World.location_graph` (`LocationGraph`) provides a flat graph of all locations. Each `Location` node has a `region_id` tag (for weather/terrain lookups) and an optional `settlement_id` tag (for economy/NPC binding). Entities hold a `location_id` and the graph resolves which region/settlement they are in. Edges between locations carry distances in meters; `travel_seconds()` computes travel time.

### NPC Memory

NPCs carry structured memory via `NpcMemory` (tags, recent, inner_state, current_conversation). Tags use `NpcTag` vocabulary — emotions (`angry`, `scared`) and relations (`hates:orc_chief`, `fears:player`). Tags are readable by both `RuleBrain` (direct checks for target selection, flee thresholds, mood-based canned dialogue) and `LlmBrain` (included in prompt context). A `MemorySummarizer` (in `llm/summarizer.py`) compresses NPC event logs into memory via a cheap LLM call, triggered after combat ends or when the `recent` field overflows 300 characters. Memory can be pre-loaded from YAML content files.

`Character.perceive(target: Entity) -> str` — observer extracts visible traits from target (name if same settlement, otherwise race + appearance). Health and conditions are surfaced through the inspect action, not baked into the perceived name (keeps event logs readable). LLM never receives raw character data, only what the observer can perceive.

## Combat System

Combat is managed by `EntitiesLayer` through `CombatState` and `BattleMap` (defined in `core/combat.py`). No separate combat layer — it's a mode within entities.

**Entry:** First attack in a location → `roll_initiative()` for all active creatures → `CombatState` created with `CombatSides` → all creatures in location get `in_combat=True`. `build_combat_sides()` (`rules/combat_sides.py`) assigns creatures to sides based on `effective_relation()` (`rules/reputation.py`): mutually FRIENDLY creatures merge into one side, HOSTILE creatures go to separate sides. `forced_opponents` (from attack handler) ensures attacker and target are always on different sides. Factionless creatures each get their own side.

**Turn order:** Initiative = d20 + DEX modifier, tiebreaker by DEX score. Order is fixed for the entire combat. Game loop iterates combatants in this order.

**Battle map:** Each `CombatState` owns a `BattleMap` — a 2D grid (coordinates in feet, 5-ft cells). Entities have `Position`s on the map. `Wall` segments block movement between adjacent cells. Perimeter walls auto-generated from map dimensions. Movement uses `rules/movement.py`: atomic direction + distance steps, D&D 5e alternating diagonal cost (5/10/5/…), wall collision. Dash is a self-buff action that adds speed to the movement pool. Abstract moves (toward/away from target) are resolved to concrete directions server-side. Budget is consumed only on a successful action, so a blocked move costs nothing. `move_to(x, y)` uses BFS pathfinding with D&D 5e diagonal costs and budget-aware stepping; player-only (excluded from LLM schemas via `provider_managed`).

**Dual awareness:** Creatures in combat get a focused prompt (HP, weapon, nearby combatants with positions/distances, round number — no weather/time/politics). Peaceful creatures get full world awareness. Two separate tool sets: combat (attack/move/dodge/flee/idle, no say — use description for flavor) and peaceful (say/attack/idle).

**Dodge:** Creatures can use the dodge action (`is_dodging` flag on `Creature`). Attackers have disadvantage against dodging targets. The flag resets at the start of the creature's next turn.

**Reactions & Opportunity Attacks:** D&D 5e reactions via `Brain.choose_reaction()` — unified ABC method (RuleBrain: always OA, LlmBrain: LLM call, PlayerBrain: interactive prompt). `TurnBudget` lives on `Creature.turn_budget` (persists between turns for reaction spending, reset at turn start). Movement handlers call `on_leave_reach` callback when mover exits enemy reach → `check_reactions` in Round asks eligible creatures to react. OA consumes reaction budget. Disengage (`is_disengaging` flag, reset at turn start) prevents OA. `ReactionTrigger` typed data is extensible for future reactions (Counterspell, Shield). `check_reactions` is recursive (reaction can trigger reaction, depth limited by 1 reaction/creature/round). `Creature.combat_position: tuple[int,int] | None` enables deterministic map placement from YAML/API — `start_combat` places fixed positions first, then scatters rest randomly. `BattleMap.set_position` raises `ValueError` on out-of-bounds.

**Exit conditions:**
- 2 consecutive rounds without any attack → auto-end
- Flee removes creature from turn order; if ≤1 left → end
- Death removes from turn order; if ≤1 left → end

**Events:** `COMBAT_STARTED` and `COMBAT_ENDED` are logged and perceived by all creatures in the location. Attack events include entity IDs so LLM can unambiguously identify participants.

## Conditions & Items

**Conditions** (`core/conditions.py`): D&D 5e status effects as a `Condition` enum (Blinded, Poisoned, Prone, Stunned, etc. + Blessed). `ConditionsMap` = `dict[Condition, int | None]` — maps active conditions to remaining rounds (`int`) or permanent (`None`). Pure mechanics in `rules/conditions.py`: `is_incapacitated()`, `effective_speed()`, `attack_advantage()`, `tick_conditions()` (decrement/expire at turn start).

**Items** (`core/items.py`): `Item` dataclass with `ItemType` (WEAPON, POTION, ARMOR, SHIELD). Weapons carry a `WeaponDef` — attack name, damage components, reach, ability, magic bonus, finesse flag, `WeaponCategory` (simple/martial), and can grant passive conditions and bonus action types while equipped. Armor carries `ArmorDef` — base AC, DEX cap, `ArmorCategory` (light/medium/heavy). Shields carry `ShieldDef` — AC bonus. `rules/weapons.py`: `get_weapon_attack()` builds `Attack` from equipped weapon, falling back to `creature.attacks` or unarmed strike (1 bludgeoning). `rules/proficiency.py`: proficiency bonus by level, weapon/armor proficiency tables per class. `Creature.equipped_weapon`/`equipped_armor`/`equipped_shield` are the active equipment; inventory holds all items. Equip/unequip actions swap equipment from inventory.

## Lairs, Encounters & Loot

**Lairs** (`core/lair.py`, hosted on `EcologyLayer`): a fixed-roster monster population pinned to a location, with a `LairState` machine `ACTIVE → DEPLETED`. While `ACTIVE`, population respawns to the roster cap on the ecology tick (`respawn_interval`); the full roster materializes when the player enters (reusing the squad materialization pattern — lair spawns are `temporary=True`, removed on death, no corpse loot). Killing the optional `core`/boss is the deterministic depletion trigger → terminal `DEPLETED` (respawn off, survives save/load); coreless lairs may use an optional `depletion_chance` rolled after a full wipe. Danger is a property of place, not party level (kenshi-style, per VISION).

**Encounters**: encounter tables are authored per-location (`encounters`) or per-region (`region_encounters`) in `ecology/monsters.yaml`. A location without its own table falls through to its region's table; a location table overrides. Resolution is load-time — `_flatten_region_defaults` (shared with `battle_map_configs`) collapses regional defaults into effective per-location tables, so `ActivationManager` stays unchanged at runtime. Each entry may carry a `time_of_day` tag (`TimeOfDay.DAY`/`NIGHT`); `ActivationManager._roll_encounters` filters with the pure `rules/encounters.is_active_at_time`, reading day/night from the geography `IS_DAYLIGHT` query (resolves location → region → latitude → `is_daylight`). Untagged entries fire at any time; spawns emit `encounter_spawned`.

**Loot** (`core/loot.py`): `InventoryHolder` is a `runtime_checkable` Protocol over anything with `inventory` + `gold` (Creature, Container); `is_lootable()` is derived state (a dead creature, or an open `Container`). `Container` (`core/container.py`) is an `Entity` sibling of `Creature` (`EntityKind.CONTAINER`) — inventory/gold/`is_open`, no HP/turn/brain — persisted by `EntitiesLayer`. The `take` action (`ActionType.TAKE`, `LootActionProvider`, handler in `rules/handlers/loot.py`) is take-all: it moves a holder's whole inventory + gold to the actor via the shared `rules/inventory.transfer_items` primitive, emitting `entity_take`. Trade is refactored onto the same primitive; loot / trade / theft are distinct access modes (no consent / consent+price / contested) over one transfer. Lair treasuries are persistent `Container`s gated behind core death.

## Class Features & Resources

Composition-based class mechanics (`core/class_features.py`). Each D&D class gets a frozen dataclass: `FighterFeatures` (fighting style, cost overrides), `RogueFeatures` (sneak attack dice), `PaladinFeatures` (fighting style, cost overrides). Each feature carries its own `collect_self_modifiers(creature)` and `collect_attack_modifiers(creature, *, melee)` — classes declare their own modifiers, and `rules/modifiers.py` iterates `creature.class_features` without knowing concrete subtypes (shared logic like fighting-style modifiers lives in `rules/fighting_style.py`). `Character.class_features: list[ClassFeatures]` — multiclass gets multiple entries. `get_feature(FeatureType)` retrieves by type.

**Fighter L1:** Fighting Style (Defense: +1 AC; Dueling: +2 melee damage; GWF: reroll 1s/2s — all via modifier pipeline). Second Wind (bonus action, 1d10+level heal, 1/short rest via ResourcePool).

**Rogue L1:** Sneak Attack (+Nd6 when advantage or ally adjacent to target, finesse/ranged only, once per turn — tracked by CombatManager). Cunning Action (Dash/Disengage as bonus action via `CostOverride`). Pure functions in `rules/sneak_attack.py`.

**Fighter L2:** Action Surge — bonus action grants an extra Action for this turn (pool of 1 use, SHORT_REST). Handler in `rules/handlers/combat.py` increments `turn_budget.actions`.

**Rogue L2:** +1 hit die → max HP bump; no new active feature (Cunning Action already at L1, diverges from PHB — documented).

**Paladin L1:** Lay on Hands only (pool of hp = 5 × level, LONG_REST).

**Paladin L2:** Fighting Style. Divine Smite (`rules/divine_smite.py`: spend a spell slot after a melee hit to add +2d8 radiant, +1d8 per slot level beyond 1). Level 1 spell slot via ResourcePool (reset on LONG_REST). Class-feature `collect_*_modifiers` methods gate on `creature.level >= required_level`, so L1 Paladin cannot use Fighting Style or Smite.

**Resource pools** (`core/resource.py`): `ResourcePool(id, max_uses, current_uses, reset_on: RestType)` on `Creature.resource_pools`. SHORT_REST / LONG_REST reset triggers. Pure management functions in `rules/resources.py`.

**Action definitions** (`core/action_defs.py`): centralized `ActionDef` registry mapping each `ActionType` to its cost, params, combat mode, and flags. `CostOverride` lets class features change action costs. Consumers (LLM tools, frontend, validation) read from this registry.

## XP & Leveling

Pure functions in `rules/leveling.py`: `xp_for_kill(cr)` (D&D 5e Monster Manual table, CR 0→10 XP … CR 30→155k), `level_for_xp(xp)` / `xp_to_next_level(xp)` (PHB thresholds, L1=0, L2=300, L3=900, …), `can_level_up(xp, level)`.

**Grant on kill:** `CombatManager.resolve_attack` emits `XP_GAINED` and increments `Character.experience` for Character-class attackers when the target has non-zero `xp_value`. XP is omniscient (like reputation drops) — not perception-gated. Sets `Character.level_up_available` when crossing a threshold.

**Level-up operation:** `perform_level_up(character, fighting_style=None)` mutates the character in-place: bumps `level`, adds hit-die-average HP, unlocks class-specific features (Fighter Action Surge pool, Paladin L2 Fighting Style/Smite/spell slot, Rogue HP only). It is stateful by design (pinned by unit-test invariant) and reachable only through `GameService.level_up_player(session_id, fighting_style)` — adapters translate HTTP to the service call and never import the rule directly. The companion `GameService.player_status(session_id, player_id=None)` returns a typed `PlayerStatusData` DTO (`service/dto.py`) with derived fields (`xp_to_next_level`, effective AC, resource pools) plus the player's `equipped` items and `inventory`, which `routes_player._player_status` then maps to the REST response.

**Transport:** `POST /api/player/sessions/{id}/level-up` (with optional `fighting_style` for Paladin L2) drives the modal. Player state payload (REST + WS) carries `experience`, `level`, `level_up_available`, `xp_to_next_level`. Frontend shows a Level Up button on the Character panel; `LevelUpModal` is class-switched (Fighter/Rogue confirm only, Paladin picks Fighting Style).

## Modifier Pipeline

Centralized derived stat computation replacing ad-hoc logic scattered across combat_manager and conditions. Data types in `core/modifiers.py`, pure functions in `rules/modifiers.py`.

**Modifier** = `(StatType, ModifierOp, value, dice, source, melee_only, ranged_only)`. `StatType`: AC, speed, attack_roll, initiative. `ModifierOp`: ADD, OVERRIDE, ADVANTAGE, DISADVANTAGE. Same `source` string = don't stack (D&D 5e rule).

**Collection:** `collect_self_modifiers(creature)` gathers modifiers affecting the creature's own stats (from conditions + equipment). `collect_defense_modifiers(creature)` gathers modifiers affecting attacks against the creature.

**Resolution:** `compute_stat(base, modifiers, stat)` — OVERRIDE wins (most restrictive), then ADD (same source takes highest, then sum). `resolve_advantage(modifiers, stat, melee)` — any advantage + any disadvantage = flat roll. `attack_modifiers(attacker, target, melee)` → `AttackModifiers` (flat mod, dice bonuses, advantage, disadvantage, force_crit, target_ac).

**Convenience API:** `effective_speed(creature)`, `effective_ac(creature)`, `attack_modifiers(attacker, target, melee)`.

## Save Schema & Reproducibility

**Save format** (Sprint 021): one versioned Pydantic envelope — `SaveGame(schema_version=1, meta, world)` in `storage/save_schema.py`. `WorldSave` carries the world seed, dice RNG state, time, last tick times, and typed layer states: each layer owns a state model (`layers/*/state.py`, `layers/entities/save_models.py`) that is the authoritative format (`extra="forbid"`), while the `Layer` ABC keeps its dict-facing `get_state()/load_state()` signatures (core stays pydantic-free). Entity payloads are a discriminated union on `entity_type` (`PlayerSave`/`NpcSave`/`CreatureSave`/`ContainerSave`) built directly from live objects in `entity_serialization.py`; combat state persists turn order, round, battle map, and sides. `save_game()` and `autosave_session()` build the same envelope; `load_game()` validates it and rejects legacy saves without `schema_version`.

**Reproducibility**: `DND_WORLD_SEED` (env; random + logged when absent) seeds the world in `game_service`; per-layer seeds are derived deterministically and passed to layer-owned `random.Random` streams. Each `GameSession` owns its dice RNG (`DND_DICE_SEED` supplies the initial seed), so concurrent sessions cannot shift one another's rolls. All RNG states are serialized into the save, so a loaded game continues the same random sequences. Same seed plus the same content produces identical world evolution.

**Autosave and round lifecycle**: per-action (create_player), session evict, shutdown, and periodic autosave all take a session snapshot through the same world-mutation gate used by round actions. File I/O happens after the snapshot is built. Load stops the old round before replacing world/RNG state and resumes only after a player reconnects. Round shutdown has a bounded timeout (`DND_ROUND_STOP_TIMEOUT_SECONDS`, default 5); on timeout the session retains the live round/thread references and load or eviction aborts safely. Autosave failures are logged, never suppressed.

## Logging

Structured logging via `structlog` (`logging_config.py`, `logging_file_dispatch.py`). `LOG_LEVEL` env var controls verbosity (default: WARNING). When `LOG_LEVEL=DEBUG` and stderr is a TTY, uses pretty console renderer; otherwise JSON. `LOG_DIR` enables denormalized JSONL file dispatch per domain tag. See [docs/LOGGING.md](docs/LOGGING.md).

## Key Principles

- **Layers depend down, never up.** Geography knows nothing about NPCs. Enforced at runtime via `query_fn`/`emit_fn` callbacks injected by World — layers can only query layers below them by index.
- **Rules are pure functions.** No state, no side effects, easy to test.
- **Brain is a strategy.** `Creature.brain` decouples decision-making from entity type. `RuleBrain` (utility scoring + canned dialogue, lives in `rules/rule_brain.py`) needs no LLM; `LlmBrain` wraps an `LlmClient`; `PlayerBrain` uses queue + callback for interactive input. `BrainType(StrEnum)` is the persisted discriminator. Brains are swappable at runtime (LOD). `core/` never imports concrete brain implementations: `core/brain.py` owns the ABC + PlayerBrain, `rules/` owns RuleBrain, `llm/` owns LlmBrain.
- **LLM is injected, not hardcoded.** `LlmBrain` receives an `LlmClient`; rule-based NPCs use no LLM at all.
- **Content is data, not code.** Worlds are composed from reusable library templates (1 template = 1 layer). Each world has a `manifest.yaml` referencing library templates or custom layers. ContentLoader resolves manifests and parses YAML into runtime objects. Fork (copy to custom) enables per-world customization.
- **Transport is a thin adapter.** The game works the same whether accessed via terminal, HTTP, or Telegram. REST API (FastAPI) is the primary adapter for frontend.
- **Two editing modes.** Between sessions: master edits YAML templates on disk. During sessions: hot controls (creature spawn/delete, HP, brain, nation/settlement patches) modify objects in memory. Saves persist state to disk.
- **Per-session i18n.** Language is set per session via `contextvars`. The global `_()` function reads the current context, so NPC LLM prompts and translated strings respect session language.
