# Layer Isolation — Plan

> Design: [layer-isolation-and-query-fn.md](../brainstorms/layer-isolation-and-query-fn.md)

## Goal

Remove `World` as god-object from layers, entities, and brains. Replace with two callbacks (`query_fn`, `emit_fn`) and push events. Enforce "query only down" at runtime.

## Phase 1 — Callback infrastructure + Layer ABC (no behavior change) DONE

Mechanical refactoring: change signatures, wire callbacks, keep all existing behavior identical. Tests must pass at every step.

### Step 1.1: Add types

`core/models.py` — add type aliases:

```python
QueryFn = Callable[[str, Query], Answer]
EmitFn = Callable[[Event], ActionResult]
```

No other files change.

### Step 1.2: Change Layer ABC

`core/layer.py` — new signatures:

```python
class Layer(ABC):
    def tick(self, delta: TimeDelta, time: GameDateTime, query_fn: QueryFn, emit_fn: EmitFn) -> list[Event]
    def handle_event(self, event: Event, query_fn: QueryFn, emit_fn: EmitFn) -> ActionResult
    # query, get_state, load_state — unchanged
```

Remove `WorldState` import from layer.py.

### Step 1.3: World creates callbacks with validation

`core/world.py`:

1. Add `_layer_index(layer_name) -> int` — returns position in `_layers` list.

2. Add `_make_query_fn(caller_layer: str) -> QueryFn`:
   - Validates: target != caller (can't query self through World)
   - Validates: target index < caller index (query only down)
   - Validates: target layer exists
   - Delegates to `self.query_layer(target, query)`

3. Add `_make_emit_fn(caller_layer: str) -> EmitFn`:
   - Validates: `event.source_layer == caller_layer`
   - Delegates to `self.handle_event(event)`

4. Update `advance_time()`:
   - Remove `state = self.get_state()` call
   - Pass `self.time`, `self._make_query_fn(layer.name)`, `self._make_emit_fn(layer.name)` to `layer.tick()`

5. Update `handle_event()`:
   - Pass `self._make_query_fn(layer.name)`, `self._make_emit_fn(layer.name)` to each `layer.handle_event()`

6. Update `_propagate_events()`:
   - Same: pass query_fn + emit_fn to `layer.handle_event()`

7. Remove `WorldState` class.

8. Remove `get_state()` method (the one returning WorldState — keep `save()`).

### Step 1.4: Update Geography layer

`layers/geography/layer.py`:

- `tick(delta, time, query_fn, emit_fn)` — replace `world_state.time` with `time` parameter. No queries needed. Returns events as before.
- `handle_event(event, query_fn, emit_fn)` — currently a no-op with events, just add params.

Straightforward — Geography reads no other layers, only uses time.

### Step 1.5: Update Settlements layer

`layers/settlements/layer.py`:

- `tick(delta, time, query_fn, emit_fn)` — currently reads `world_state.layer_states["geography"]` and `world_state.layer_states["politics"]` for weather and nation data.
  - Replace geography reads with: `query_fn("geography", Query("weather", {"region_id": rid}))`
  - Replace politics reads with: `query_fn("politics", Query("nation_info", {"nation_id": nid}))` and `query_fn("politics", Query("region_owner", {"region_id": rid}))`
  - This is query **down** (settlements index > geography/politics index) — validation passes.
- `handle_event(event, query_fn, emit_fn)` — add params, behavior unchanged.

Need to verify the layer order in `World.__init__`. Current order in `game_service.py:108`:
```python
layers=[geography, settlements_layer, politics, entities_layer]
```
So index: geography=0, settlements=1, politics=2, entities=3.

**Problem**: Settlements (index 1) queries Politics (index 2) — that's querying **up**. Either:
- (a) Reorder: geography, politics, settlements, entities — so settlements can query politics (below it)
- (b) Politics pushes data to settlements via events

Option (a) is simpler and correct: politics logically comes before settlements (nations exist before towns depend on them). Reorder in `game_service.py` and `cli_loop.py`.

After reorder: geography=0, politics=1, settlements=2, entities=3.

### Step 1.6: Update Politics layer

`layers/politics/layer.py`:

- `tick(delta, time, query_fn, emit_fn)` — currently doesn't read WorldState at all. Just add params, use `time` if needed.
- `handle_event(event, query_fn, emit_fn)` — add params.

Politics has `region_income_fn` callback from Settlements (set in game_service.py:98). This is an existing cross-layer callback for war strength calculations — leave it for now, mark as tech debt for Phase 2 (should become a push event from settlements).

### Step 1.7: Update Entities layer — bridged

`layers/entities/layer.py`:

- `tick(delta, time, query_fn, emit_fn)` — new signature. **But** internally still calls `entity.take_turn(self._world)`. Phase 1 does NOT change the NPC turn flow.
  - Store `query_fn` and `emit_fn` on `self` temporarily so they're available during the tick.
  - `self._world` stays for now — removed in Phase 2.
- `handle_event(event, query_fn, emit_fn)` — add params. Combat resolution may need query_fn (e.g., to look up entity positions). Currently it accesses `self._entities` directly, so no change needed.

### Step 1.8: Update tests

All layer tests create layers and call `tick(delta, world_state)` / `handle_event(event)`. Update every call site:

- Replace `world_state` with `time` + `query_fn` + `emit_fn`
- `query_fn` in tests: mock/lambda that returns expected data, or a real helper
- `emit_fn` in tests: mock/lambda that collects emitted events

Files:
- `tests/test_geography_layer.py`
- `tests/test_politics_layer.py`
- `tests/test_settlements_layer.py`
- `tests/test_npc_layer.py`
- `tests/test_game_loop.py`
- `tests/test_api.py`
- `tests/test_combat.py`
- `tests/test_combat_awareness.py`
- Any other test that constructs World or calls layer methods

### Step 1.9: Cleanup

- Remove `WorldState` from all imports
- Verify `make check` passes (lint + typecheck + tests)
- Verify no remaining references to `world_state` in layer code

### Acceptance criteria

- `make check` passes
- No layer imports `World` or `WorldState`
- `World` creates validated callbacks — test that querying up raises `LayerError`
- Layer order: geography < politics < settlements < entities
- All existing gameplay works identically (no behavior change)

### Files touched

| File | Change |
|------|--------|
| `core/models.py` | Add `QueryFn`, `EmitFn` types |
| `core/layer.py` | New `tick`/`handle_event` signatures, remove WorldState import |
| `core/world.py` | Callback factories, validation, remove WorldState, remove `get_state()` |
| `layers/geography/layer.py` | New tick/handle_event signature, use `time` param |
| `layers/politics/layer.py` | New tick/handle_event signature |
| `layers/settlements/layer.py` | New tick/handle_event signature, query_fn instead of layer_states |
| `layers/entities/layer.py` | New tick/handle_event signature (bridged, _world stays) |
| `service/game_service.py` | Reorder layers: geography, politics, settlements, entities |
| `adapters/cli_loop.py` | Reorder layers if it builds World directly |
| Tests (8+ files) | Update all tick/handle_event call sites |

---

## Phase 2 — Brain isolation DONE

### Goal

Remove `World` from Brain, Creature.take_turn, Creature.execute_action, build_awareness, and build_combat_awareness. EntitiesLayer becomes the orchestrator: builds awareness via query_fn, passes structured data to brain, executes actions via emit_fn. `_world` reference removed from EntitiesLayer.

### Design decisions

1. **Awareness is a dataclass**, not a dict. Two models: `PeacefulAwareness` and `CombatAwareness`. EntitiesLayer checks `creature.in_combat` and builds the right one.
2. **Events are structured** — dataclasses, not strings. Brain receives typed event objects, LlmBrain serializes them for prompts.
3. **perceive_by_id** — EntitiesLayer owns entities, builds descriptions internally without query_fn.
4. **location_graph** data (location name) goes into awareness. Brain never touches location_graph.
5. **execute_action stays on Creature** with `emit_fn` instead of `World`. Polymorphism-ready: different creature subclasses can override execute_action for class-specific abilities (spells, monster actions). `emit_fn` is a minimal contract — one callback for side effects.
6. **Brain.choose_action(creature, awareness, events) → Action** — pure function, no side effects.

### Step 2.1: Awareness dataclasses

`core/awareness.py` — new file:

```python
@dataclass(frozen=True)
class NearbyEntity:
    id: str
    description: str
    is_wounded: bool = False

@dataclass(frozen=True)
class CombatEntity(NearbyEntity):
    distance_ft: int = 0
    direction: str = ""

@dataclass(frozen=True)
class PeacefulAwareness:
    hour: int
    day: int
    month: int
    year: int
    weather: dict[str, object] | None
    location_name: str
    region_name: str
    settlements: list[dict[str, object]] | None
    territory_owner: str | None
    nation_info: dict[str, object] | None
    nearby: list[NearbyEntity]

@dataclass(frozen=True)
class CombatAwareness:
    self_hp: int
    self_max_hp: int
    self_ac: int
    self_speed: int
    self_weapon: str
    self_weapon_damage: str
    nearby: list[CombatEntity]
    round_number: int
    walls: list[str]
```

### Step 2.2: Perceived event dataclass

`core/awareness.py` (same file) or `layers/entities/perception.py`:

```python
@dataclass(frozen=True)
class PerceivedEvent:
    description: str          # human-readable text (for LLM prompts)
    event_type: EventType     # structured type (for RuleBrain logic)
    actor_id: str | None = None
    target_id: str | None = None
    data: dict[str, object] = field(default_factory=dict)
```

`perceive_event()` returns `PerceivedEvent` instead of `str`. RuleBrain can check `event.event_type == ENTITY_SAY` directly, LlmBrain uses `event.description`.

### Step 2.3: Brain ABC — new signature

`core/brain.py`:

```python
class Brain(ABC):
    @abstractmethod
    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
```

Remove `World` import from brain.py entirely.

### Step 2.4: RuleBrain — use structured awareness

`core/brain.py`:

- `choose_action(creature, awareness, events)` — check `isinstance(awareness, CombatAwareness)` for combat mode.
- `_peaceful_action(creature, events)` — scan `events` for `event_type == ENTITY_SAY` instead of querying `world.query_layer("entities", "new_raw_events")`. No more world access.
- `_choose_combat_action(creature, awareness)` — already takes awareness dict, switch to `CombatAwareness` fields. Minimal changes.

### Step 2.5: LlmBrain — use structured awareness

`llm/brain.py`:

- `choose_action(creature, awareness, events)` — branch on `isinstance(awareness, CombatAwareness)`.
- Combat path: `build_npc_combat_prompt(npc_data, awareness)` — adapt to accept `CombatAwareness` dataclass.
- Peaceful path: `build_npc_system_prompt(npc_data, awareness, nearby)` — `awareness` is `PeacefulAwareness`, `nearby` comes from `awareness.nearby`.
- Events: serialize `[e.description for e in events]` for the LLM turn prompt.
- Remove `build_awareness`, `build_combat_awareness`, `world.query_layer` calls entirely.
- `npc_data` enrichment (activity, location_label) — comes from awareness fields, not `world.time.hour` / `world.location_graph`.

### Step 2.6: Creature.execute_action — emit_fn instead of World

`core/character.py`:

```python
def execute_action(self, action: Action, emit_fn: EmitFn) -> bool:
    if action.name == "say":
        emit_fn(Event(event_type=EventType.ENTITY_SAY, source_layer="entities",
                       data={"entity_id": self.id, "text": action.params.get("text", "")}))
        return True
    # ... same pattern for attack, dodge, flee, move, dash
```

Remove `World` from `execute_action` signature. Remove `take_turn` method — EntitiesLayer orchestrates directly.

### Step 2.7: EntitiesLayer — orchestrator

`layers/entities/layer.py`:

1. **Remove `_world` field and `set_world()` method.**

2. **New `_build_peaceful_awareness(creature, time, query_fn)` method:**
   - `query_fn("geography", Query("weather", ...))` for weather
   - `query_fn("geography", Query("region_info", ...))` for region/location names
   - `query_fn("settlements", Query("region_settlements", ...))` for settlements
   - `query_fn("politics", Query("region_owner", ...))` and `query_fn("politics", Query("nation_info", ...))` for politics
   - Nearby entities: internal `self._entities` lookup + `observer.perceive(target)` — no query needed
   - Returns `PeacefulAwareness`

3. **New `_build_combat_awareness(creature)` method:**
   - All data is internal: combat state from `self._combat`, entity positions from battle map, distances from rules
   - `observer.perceive(target)` for descriptions — internal, no query
   - Returns `CombatAwareness`

4. **New `_get_perceived_events(creature)` method:**
   - Calls existing `get_new_raw_events(creature)` for raw events
   - Runs `perceive_event()` on each → returns `list[PerceivedEvent]`

5. **Rewritten `tick()`:**
   ```python
   def tick(self, delta, time, query_fn, emit_fn):
       for creature in active_npcs:
           if creature.in_combat:
               awareness = self._build_combat_awareness(creature)
           else:
               awareness = self._build_peaceful_awareness(creature, time, query_fn)
           events = self._get_perceived_events(creature)
           action = creature.brain.choose_action(creature, awareness, events)
           creature.execute_action(action, emit_fn)
   ```

6. **`perceive_by_id` usage** — removed from Character. EntitiesLayer calls `observer.perceive(target)` directly since it has both entities.

### Step 2.8: Remove perceive_by_id and build_awareness from Character

`core/character.py`:

- Delete `perceive_by_id(entity_id, world)` method
- Delete `build_awareness(world, location_id)` function
- Delete `build_combat_awareness(world, entity)` function
- Delete `take_turn(world)` method
- Keep `perceive(target)` (pure, no World)
- Keep `execute_action(action, emit_fn)` (updated signature)

### Step 2.9: World.__init__ — remove set_world bridge

`core/world.py`:

- Remove the `set_world` loop in `__init__` (lines 33-36)

### Step 2.10: Update tests

- `tests/test_rule_brain.py` — pass awareness dataclass + events instead of mock World
- `tests/test_npc_layer.py` — tick no longer needs `_world`, remove mock world setup
- `tests/test_game_loop.py` — if it calls take_turn, update
- Any test importing `build_awareness`, `build_combat_awareness`, `perceive_by_id` — update to new locations/signatures
- Add tests for `_build_peaceful_awareness` and `_build_combat_awareness` on EntitiesLayer

### Step 2.11: Cleanup

- Remove `World` import from `core/brain.py`, `core/character.py` (runtime), `llm/brain.py`
- Verify no remaining `_world` references in layers
- `make check` passes

### Acceptance criteria

- `make check` passes
- No Brain or Creature imports `World`
- EntitiesLayer has no `_world` field or `set_world()` method
- `build_awareness` and `build_combat_awareness` live on EntitiesLayer, use query_fn
- Brain.choose_action receives structured `PeacefulAwareness | CombatAwareness` + `list[PerceivedEvent]`
- Creature.execute_action uses `emit_fn`, not `World`
- All existing gameplay works identically

### Files touched

| File | Change |
|------|--------|
| `core/awareness.py` | NEW — PeacefulAwareness, CombatAwareness, NearbyEntity, CombatEntity, PerceivedEvent |
| `core/brain.py` | New choose_action signature, RuleBrain uses awareness dataclass + events |
| `core/character.py` | Remove take_turn, perceive_by_id, build_awareness, build_combat_awareness; execute_action takes emit_fn |
| `llm/brain.py` | New choose_action signature, use awareness dataclass, remove world queries |
| `layers/entities/layer.py` | Remove _world/set_world, add _build_*_awareness, rewrite tick() as orchestrator |
| `layers/entities/perception.py` | perceive_event returns PerceivedEvent |
| `core/world.py` | Remove set_world loop |
| `llm/prompts.py` | Accept awareness dataclasses instead of raw dicts (if needed) |
| Tests (5+ files) | Update brain tests, entity layer tests, remove mock World from brain tests |

---

## Phase 3+ — Not yet detailed

See [brainstorm](../brainstorms/layer-isolation-and-query-fn.md) for the full picture. Remaining phases to be planned after Phase 2 lands:

- **Phase 3**: PlayerBrain — player as regular Brain (CLI + API variants), unify wait/idle, simplify game_loop to just `advance_time`
- **Phase 4**: Push events — Settlements emits census for Politics, remove `region_income_fn` callback
- **Phase 5**: Combat turn order moves into EntitiesLayer.tick(), game_loop becomes trivial
