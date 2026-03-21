# Round System — Plan

> Design: [round-system.md](../brainstorms/round-system.md)
> Supersedes Phase 3–5 from [layer-isolation.md](layer-isolation.md)

## Goal

Replace game_loop with a Round orchestrator. Player becomes a regular Brain. WebSocket as primary transport. Multiple actions per turn. Turn-based mode. Fast-forward. Level 2 consciousness in EntitiesLayer.tick().

---

## Phase 3a — Round orchestrator + PlayerBrain DONE

### Goal

Round orchestrator replaces game_loop. PlayerBrain reads actions from a queue. One action per turn (existing behavior). CLI temporarily puts actions into queue directly. All tests pass, gameplay identical.

### Design decisions

1. **Round is a separate class**, not part of World. World owns layers and time. Round owns the turn cycle and activation.
2. **PlayerBrain is one class** — not CLI/API variants. It reads from a queue (`asyncio.Queue` or `queue.Queue`). Transport (WebSocket, CLI) puts actions into the queue.
3. **One action per turn for now** — `choose_action()` signature unchanged. Multiple actions per turn deferred to Phase 3c.
4. **game_loop.py replaced** — `run_game_loop()` replaced by `Round.run()` or similar.
5. **CLI adapter** — temporarily puts actions into PlayerBrain's queue directly (later becomes WS client in Phase 3b).

### Step 3a.1: PlayerBrain

`core/brain.py` — new `PlayerBrain` class:

```python
class PlayerBrain(Brain):
    """Brain that reads actions from an external queue."""

    def __init__(self) -> None:
        self._action_queue: queue.Queue[Action] = queue.Queue()
        self._awareness_callback: Callable[[PeacefulAwareness | CombatAwareness, list[PerceivedEvent]], None] | None = None

    def set_awareness_callback(self, cb: Callable) -> None:
        """Transport sets this to receive awareness when it's the player's turn."""
        self._awareness_callback = cb

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        # Push awareness to transport (so client sees what's happening)
        if self._awareness_callback:
            self._awareness_callback(awareness, events)
        # Block until transport provides an action
        return self._action_queue.get()

    def submit_action(self, action: Action) -> None:
        """Called by transport to provide the player's chosen action."""
        self._action_queue.put(action)
```

### Step 3a.2: Round orchestrator

`core/round.py` — new file:

```python
class Round:
    def __init__(self, world: World, entities_layer: EntitiesLayer) -> None:
        self._world = world
        self._entities = entities_layer

    def run_round(self) -> list[Event]:
        """Execute one round: all active entities act, then advance time."""
        query_fn = self._world._make_query_fn("entities")
        emit_fn = self._world._make_emit_fn("entities")
        time = self._world.time

        for creature in self._entities.get_active_creatures():
            if creature.brain is None:
                continue
            self._entities.run_creature_turn(creature, time, query_fn, emit_fn)

        return self._world.advance_time(TimeDelta.from_rounds(1))

    def run_loop(self) -> None:
        """Run rounds forever (main game loop replacement)."""
        while True:
            active = self._entities.get_active_creatures()
            if not active:
                break
            self.run_round()
```

### Step 3a.3: Wire PlayerBrain into PlayerCharacter

`core/player.py`:

- Remove `take_turn()`, `_peaceful_turn()`, `_combat_turn()`, `_build_awareness()`, `_build_combat_awareness()`, `_cmd_look()`, `_cmd_wait()`, `_cmd_status()`
- Remove `input_fn`, `output_fn` fields
- Keep `to_save_data()`, `to_full_save_data()`, `load_save_data()`
- PlayerCharacter gets `brain = PlayerBrain()` at creation time (in content_loader or game_service)

### Step 3a.4: EntitiesLayer.tick() — stop skipping player

`layers/entities/layer.py`:

- Remove `isinstance(entity, PlayerCharacter)` check in `tick()`
- All active creatures (including player) are handled uniformly by Round
- `tick()` no longer runs creature turns at all (Round does that). Tick becomes empty or housekeeping-only for now.

### Step 3a.5: Update GameService

`service/game_service.py`:

- Player action flow changes: instead of directly emitting events via `world.handle_event()`, service translates command text into `Action` and calls `player_brain.submit_action(action)`
- Round must run in a background thread/task, blocking on PlayerBrain.choose_action()
- OR: service explicitly calls `round.run_round()` after player submits action (simpler, synchronous, keeps request-response model for now)
- Second option is simpler and doesn't change the API contract. WebSocket async model comes in Phase 3b.

Synchronous approach:
```python
def player_action(self, session_id, text):
    action = self._parse_action(text)
    player_brain.submit_action(action)
    events = round.run_round()
    return MasterResponse(...)
```

### Step 3a.6: Move formatting to service/transport

Awareness formatting (`_format_awareness`, `_format_combat_awareness`) moves out of PlayerCharacter. Options:
- Into service layer (for REST/API responses)
- Into a dedicated formatter module
- Clients receive raw awareness JSON and format themselves

For now: service returns `dataclasses.asdict(awareness)` in API responses. CLI adapter formats for terminal. PlayerCharacter has no formatting logic.

### Step 3a.7: Update CLI adapter

`adapters/cli_loop.py` (or new `adapters/cli.py`):

- No longer calls `run_game_loop()`
- Creates `Round`, runs `round.run_loop()` in a thread
- PlayerBrain's awareness_callback prints to terminal
- Reads input, parses to Action, calls `player_brain.submit_action()`

### Step 3a.8: Update tests

- Tests that used `run_game_loop()` → use `Round`
- Tests that called `player.take_turn(world)` → use `PlayerBrain.submit_action()` + `round.run_round()`
- Brain tests for PlayerBrain
- Remove mock World from player tests

### Step 3a.9: Cleanup

- Remove `game_loop.py` (replaced by `core/round.py`)
- Remove `World` import from `core/player.py`
- Verify `make check` passes

### Acceptance criteria

- `make check` passes
- PlayerCharacter has no `take_turn()`, no `_build_awareness()`, no `World` import
- Round orchestrator runs all active creatures uniformly
- Player actions go through PlayerBrain queue
- CLI and API both work through PlayerBrain
- No behavior change from user perspective

### Files touched

| File | Change |
|------|--------|
| `core/brain.py` | Add `PlayerBrain` class |
| `core/round.py` | NEW — Round orchestrator |
| `core/player.py` | Remove take_turn, awareness building, formatting, input/output |
| `layers/entities/layer.py` | tick() stops skipping player, stops running creature turns |
| `service/game_service.py` | Route actions through PlayerBrain + Round |
| `service/commands_*.py` | Return Actions instead of emitting events directly |
| `adapters/cli_loop.py` | Use Round + PlayerBrain |
| `game_loop.py` | REMOVED |
| Tests (5+ files) | Update to new Round/PlayerBrain API |

---

## Phase 3b — WebSocket adapter DONE

### Goal

WebSocket as primary transport. Protocol: awareness → action → round_result. REST stays for stateless queries.

### What was done

1. **PlayerBrain** — переведён с callback (`TurnHandler`) на `queue.Queue` + `on_turn` callback. `submit_action()` кладёт в очередь, `choose_action()` блокирует на `.get()`. Тип `TurnHandler` удалён, заменён на `OnTurnCallback` (возвращает `None`).
2. **Round** — добавлены `stop()` (флаг для выхода из loop) и `set_on_round_end(callback)` (вызывается после каждого раунда).
3. **WS endpoint** (`adapters/api/routes_ws.py`) — `GET /api/ws/{session_id}`. Round в daemon-потоке, awareness отправляется через `asyncio.run_coroutine_threadsafe`, actions приходят из WS. Queries обрабатываются без потребления хода.
4. **CLI adapter** — минимальное обновление: `CliTurnHandler` принимает brain, вызывает `submit_action()` вместо return.
5. **Тесты** — 10 новых (4 PlayerBrain queue + 6 WebSocket endpoint).

### Отклонения от исходного плана

1. **`queue.Queue` вместо `asyncio.Queue`** — Round остаётся sync, живёт в отдельном потоке. Мост через `asyncio.run_coroutine_threadsafe`. Не потребовалось делать Brain/Round async.
2. **CLI НЕ переписан как WS-клиент** — отложено. CLI по-прежнему работает напрямую через Round + PlayerBrain (on_turn callback печатает, читает input, вызывает submit_action).
3. **Протокол упрощён** — нет отдельного `action_result` (один action = конец хода). `action_result` будет добавлен в Phase 3c вместе с multiple actions per turn.
4. **Тип сообщения `awareness` переименован в `turn`** — содержит mode + awareness + events.
5. **REST `player_action` endpoint не менялся** — backward compat через существующий REST сохраняется as-is.
6. **Session не хранит Round/thread** — lifecycle управляется WS handler напрямую (создаёт и убивает при connect/disconnect).

### Actual protocol

```
← {"type": "turn", "mode": "peaceful|combat", "awareness": {...}, "events": [...]}
→ {"type": "action", "name": "attack", "params": {"target_id": "goblin1"}}
← {"type": "round_result", "events": [...]}
← {"type": "turn", ...}

→ {"type": "query", "name": "look|status|map|perception|combat"}
← {"type": "query_result", "query": "look", "data": {...}}

← {"type": "error", "message": "..."}
← {"type": "game_over"}
```

### Files touched

| File | Change |
|------|--------|
| `core/brain.py` | PlayerBrain: callback → queue + on_turn. `TurnHandler` → `OnTurnCallback` |
| `round.py` | `stop()`, `set_on_round_end()`, `_stop_flag` |
| `adapters/api/routes_ws.py` | NEW: WebSocket endpoint |
| `adapters/api/app.py` | Register ws_router |
| `adapters/cli_loop.py` | Minimal update for new PlayerBrain API |
| `tests/test_player_brain.py` | NEW: queue pattern tests |
| `tests/test_ws.py` | NEW: WebSocket endpoint tests |
| `tests/test_game_loop.py` | Updated for new PlayerBrain constructor |

---

## Phase 3c — Multiple actions per turn + reactions DONE

### Goal

Multi-action turns with budget enforcement. Reactions as interrupt mini-turns. Entity-level queries eliminated — everything is an Action (some cost 0). Unified turn loop for combat and peaceful modes.

### Design decisions

1. **Everything is an Action** — no entity-level queries. look, status, map — Actions with zero cost. Brain always returns Action via choose_action(). Cross-layer queries (world.query) remain — they're infrastructure, not entity behavior.
2. **choose_action() signature unchanged** — returns one Action at a time. Called in loop until brain returns `end_turn`.
3. **TurnBudget tracks resources** — `actions: int` (default 1, Fighter Extra Attack gives more), `bonus_actions: int` (default 1), `movement_remaining: int` (from creature speed), `reaction: int` (default 1, consumed by reactions). All ints, not bools — some features grant additional uses.
4. **Round enforces budget** — before execute, Round checks `rules.action_cost(action)` and `budget.consume(cost)`. Illegal action → rejected. Concrete cost tables (which class gets how many actions) deferred to rules/, but the enforce skeleton is in 3c.
5. **Reactions are interrupt mini-turns** — triggered by events (opportunity attack, counterspell, shield). Round pauses the current turn, asks the reacting creature via the same `choose_action()` with awareness containing only available reactions + skip. If not skip: execute, `budget.reaction -= 1`. Then resume interrupted turn.
6. **Peaceful and combat use the same loop** — one `run_creature_turn` implementation, budget differs by context (combat has stricter rules, peaceful may have unlimited free actions). No separate handlers.
7. **Awareness includes budget** — CombatAwareness/PeacefulAwareness get a `turn_budget: TurnBudget` field so brains know what's left. LLM sees it in prompt, RuleBrain checks programmatically.
8. **Round owns budget, not Creature** — TurnBudget is a local variable of `run_creature_turn()`. It's runtime state of one turn, not a creature property. Creature provides `speed` (base movement), Round computes budget from it.

### Turn loop (in Round)

```python
def run_creature_turn(self, creature, time, query_fn, emit_fn) -> list[Action]:
    budget = TurnBudget(
        actions=rules.get_num_actions(creature),
        bonus_actions=rules.get_num_bonus_actions(creature),
        movement_remaining=creature.speed,
    )
    actions: list[Action] = []

    while True:
        awareness = self._entities.build_awareness(creature, time, query_fn)
        awareness.turn_budget = budget
        events = self._entities.get_perceived_events(creature)

        action = creature.brain.choose_action(creature, awareness, events)
        if action.name == "end_turn":
            break

        cost = rules.action_cost(action)
        budget.consume(cost)          # raises/rejects if over budget
        creature.execute_action(action, emit_fn)
        actions.append(action)

        # Hook: on_action_executed(creature, action, budget) → WS sends action_result

    return actions
```

### Reaction flow (in Round)

```python
# During someone's turn, an event triggers a possible reaction
def check_reactions(self, trigger_event, candidates, time, query_fn, emit_fn):
    for creature in candidates:
        if creature.budget.reaction <= 0:
            continue
        available = rules.available_reactions(creature, trigger_event)
        if not available:
            continue
        # Mini-turn: awareness with only reaction options + skip
        awareness = self._entities.build_awareness(creature, time, query_fn)
        awareness.available_actions = available + [Action("skip")]
        events = [trigger_event]
        action = creature.brain.choose_action(creature, awareness, events)
        if action.name != "skip":
            creature.execute_action(action, emit_fn)
            creature.budget.reaction -= 1
```

### Brain behavior per type

| Brain | Turn behavior | Reaction behavior |
|-------|--------------|-------------------|
| **RuleBrain** | 1 action → end_turn (simple). Later: attack + move → end_turn | Check reaction table, take best or skip |
| **LlmBrain** | LLM sees budget in prompt, decides sequence. attack → move → end_turn | LLM decides from available reactions |
| **PlayerBrain** | Each choose_action() blocks on queue. Client sends end_turn explicitly | Same — blocks on queue, client picks reaction or skip |

### WS protocol update

```
← turn:          {awareness, budget, events}
→ action:        {name: "attack", params: {target_id: "goblin1"}}
← action_result: {events, updated_budget, awareness}     # NEW — after each action
→ action:        {name: "move", params: {x: 5, y: 3}}
← action_result: {events, updated_budget, awareness}
→ action:        {name: "end_turn"}
← round_result:  {events}                                # after ALL creatures acted

# Reaction interrupt (injected mid-turn):
← reaction_prompt: {trigger_event, available_reactions, awareness}
→ action:          {name: "opportunity_attack", params: {...}}   # or "skip"
← action_result:   {events}
# ... interrupted turn resumes
```

### Key steps

1. TurnBudget dataclass + rules.action_cost() skeleton
2. Round.run_creature_turn() → multi-action loop with budget enforce
3. Add end_turn Action constant
4. Awareness gets turn_budget field
5. RuleBrain: action → end_turn. PlayerBrain: unchanged (already loops via queue)
6. Remove entity-level query handling from EntitiesLayer (look/status become Actions)
7. Reaction check_reactions() in Round — interrupt flow
8. WS protocol: action_result message type between actions
9. Update tests

### Files touched

| File | Change |
|------|--------|
| `core/turn_budget.py` | NEW — TurnBudget dataclass |
| `rules/actions.py` | NEW — action_cost(), get_num_actions(), available_reactions() skeletons |
| `round.py` | run_creature_turn → multi-action loop + check_reactions |
| `core/action.py` | Add END_TURN, SKIP constants |
| `core/brain.py` | RuleBrain: action → end_turn after single action |
| `llm/brain.py` | LlmBrain: budget in prompt, end_turn after sequence |
| `layers/entities/layer.py` | build_awareness public, remove query handling for look/status |
| `layers/entities/models.py` | Awareness gets turn_budget field |
| `adapters/api/routes_ws.py` | action_result + reaction_prompt message types |
| `service/commands_world.py` | look/status become Actions, not queries |
| Tests | Multi-action turns, budget enforcement, reactions |

### What was done

1. **TurnBudget** (`core/turn_budget.py`) — `actions: int`, `bonus_actions: int`, `movement_remaining: int`, `reaction: int`. `ActionCost` + `consume()`/`can_afford()`.
2. **Action cost rules** (`rules/actions.py`) — `action_cost()`, `get_num_actions()`, `get_num_bonus_actions()`. attack/dodge/dash cost 1 action, say/idle/end_turn free, move costs 5ft.
3. **END_TURN, SKIP** sentinels in `core/action.py`.
4. **Awareness** — `PeacefulAwareness`/`CombatAwareness` now non-frozen, have `turn_budget: TurnBudget | None`.
5. **Round.run_creature_turn** — multi-action loop: build awareness (with budget) → choose_action → enforce budget → execute → repeat until end_turn or budget exhausted. `on_action` callback for WS action_result.
6. **Round.check_reactions** — skeleton for reaction interrupts (not wired to trigger points yet).
7. **RuleBrain** — returns `end_turn` instead of `idle` in peaceful mode; checks `budget.actions <= 0` before combat action.
8. **WS protocol** — `action_result` message between actions within a turn; `budget` in `turn` message; `query` message type removed (action→awareness only).
9. **GameService cleanup** — removed `player_action()`/`_dispatch_action()`, `CombatCommands`, `WorldCommands` mixins, `MasterResponse`. Removed REST endpoints: POST /action, GET /perception, GET /events, GET /combat, GET /map. Removed legacy `adapters/cli.py`.
10. **Bug fix** — `get_perceived_events()` now advances `_last_seen_log_index` to prevent infinite loop in multi-action turn (RuleBrain would repeat say forever on stale events).
11. **WS robustness** — `_ws_send_from_thread()` helper catches send errors on disconnect.
12. **REST schemas** — `attacks` field added to `CreatePlayerRequest` and `SpawnNpcRequest`.
13. **Live test script** (`scripts/live_test.py`) — 13-step integration test covering REST + WS: session, player, NPC spawn, combat with ranged weapons, flee, peaceful turns, save/load.

### Deviations from plan

1. **Entity-level queries NOT removed** — cross-layer queries stay (infrastructure). WS query message type removed. REST query endpoints removed. look/status as zero-cost Actions deferred (requires GameService command routing refactor).
2. **Reactions skeleton only** — `check_reactions()` exists but no trigger points wired (opportunity attacks, counterspell etc). Will connect when specific D&D rules are implemented.
3. **EntitiesLayer.tick()** still runs NPC turns — double-execution with Round. Harmless (RuleBrain returns end_turn immediately) but wasteful. Should be cleaned up in 3d.

---

## Phase 3d — Turn-based mode, fast-forward, Level 2 tick ⬜

### Goal

Free vs turn-based round modes. Fast-forward when no active entities. Level 2 consciousness in EntitiesLayer.tick().

### Turn-based mode

- Round knows current mode: `free` or `turn_based`
- Turn-based: initiative order, strict turn sequence (BG3 style)
- Free: all active act "simultaneously" (order doesn't matter)
- Combat = turn-based + combat action restrictions
- Triggers: entering combat, DM command, trap, stealth

### Fast-forward

- When all entities inactive: jump to nearest layer tick instead of iterating 6-second rounds
- Each layer reports `next_tick_delta` — jump to minimum
- After jump: check reactivation triggers
- If someone activated → exit fast-forward, resume normal rounds

### Level 2 consciousness in EntitiesLayer.tick()

- EntitiesLayer.tick() handles world events for inactive entities
- Event arrives (war, disaster) → check wake triggers per NPC
- Triggered NPCs get cheap batch LLM call → update traits/schedule
- Some may upgrade to Level 3 (active = True)
- This is the "living world" background process

### Files touched

| File | Change |
|------|--------|
| `core/round.py` | Add mode (free/turn_based), fast-forward logic |
| `layers/entities/layer.py` | tick() becomes Level 2 processor |
| `core/models.py` | RoundMode enum |

---

## Phase 4+ — Not yet detailed

Remaining work from layer-isolation.md and future:

- **Push events**: Settlements emits census for Politics, remove `region_income_fn` callback
- **Master as LLM**: DM layer that interprets free-text player input
- **Random encounters**: spawn during travel/wait
- **NPC tiers**: BACKGROUND / IMPORTANT / KEY with different tick frequencies
