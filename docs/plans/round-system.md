# Round System — Plan

> Design: [round-system.md](../brainstorms/round-system.md)
> Supersedes Phase 3–5 from [layer-isolation.md](layer-isolation.md)

## Goal

Replace game_loop with a Round orchestrator. Player becomes a regular Brain. WebSocket as primary transport. Multiple actions per turn. Turn-based mode. Fast-forward. Level 2 consciousness in EntitiesLayer.tick().

---

## Phase 3a — Round orchestrator + PlayerBrain ⬜

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

## Phase 3b — WebSocket adapter ⬜

### Goal

WebSocket as primary transport. Protocol: awareness → action → result → round_end. REST stays for stateless queries. CLI becomes a WS client.

### Design decisions

1. **FastAPI WebSocket** endpoint alongside existing REST.
2. **Round runs in asyncio task** per session — blocks on PlayerBrain.choose_action() (which awaits the queue).
3. **PlayerBrain queue becomes asyncio.Queue** for async compatibility.
4. **Queries** (look, status, map) handled inline without consuming a turn.

### Key steps

- Add `POST /sessions/{id}/ws` WebSocket endpoint
- Round loop runs as asyncio task per session
- PlayerBrain.awareness_callback sends JSON over WebSocket
- Client sends action JSON, handler puts into PlayerBrain queue
- Client sends query JSON, handler responds immediately
- CLI adapter: connect to WS, render awareness as text, send actions as JSON
- REST `player_action` endpoint kept for backward compat (wraps submit + wait for round)

### Protocol

```
← {"type": "awareness", "mode": "free", "data": {...}, "events": [...]}
→ {"type": "action", "name": "attack", "params": {"target_id": "goblin1"}}
← {"type": "action_result", "success": true, "events": [...]}
← {"type": "round_end"}
← {"type": "awareness", ...}

→ {"type": "query", "name": "look"}
← {"type": "query_result", "name": "look", "data": {...}}
```

### Files touched

| File | Change |
|------|--------|
| `adapters/api.py` | Add WebSocket endpoint |
| `core/brain.py` | PlayerBrain queue → asyncio.Queue, choose_action → async or threaded |
| `core/round.py` | Async-compatible run_loop |
| `adapters/cli.py` | Rewrite as WS client |

---

## Phase 3c — Multiple actions per turn ⬜

### Goal

Brain can take multiple actions per turn (Action + Bonus Action + Movement). choose_action() called in loop until end_turn.

### Design decisions

1. **choose_action() signature unchanged** — returns one Action at a time.
2. **Round calls choose_action() in loop** until brain returns `Action(name="end_turn")`.
3. **After each action**: execute, update awareness, call choose_action() again.
4. **Action budget tracking** (optional): Round or EntitiesLayer tracks what's been used this turn (action, bonus_action, movement, reaction). Enforce D&D 5e rules.

### Key steps

- Round.run_creature_turn() becomes a loop: choose → execute → update awareness → repeat
- New `end_turn` Action type
- WebSocket protocol: multiple action/result exchanges before round_end
- RuleBrain and LlmBrain updated to use end_turn
- PlayerBrain: client sends end_turn explicitly

### Files touched

| File | Change |
|------|--------|
| `core/round.py` | Loop in run_creature_turn until end_turn |
| `core/action.py` | Add END_TURN action |
| `core/brain.py` | RuleBrain returns end_turn after single action; PlayerBrain unchanged |
| `llm/brain.py` | LlmBrain returns end_turn after action sequence |
| `layers/entities/layer.py` | Awareness rebuild between actions |

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
