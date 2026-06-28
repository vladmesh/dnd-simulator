# E2E Report: sprint018-phase2

**Date:** 2026-06-28
**Flags:** --no-llm
**Sections tested:** 1 (session setup) + auto-discovered loot/take flow + combat regression
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, default content (level_up_test arena)

## Summary

- Scenarios: 7 tested, 7 passed, 0 failed
- Quick fixes: 0 applied during E2E (two fixes landed earlier in close-phase, see below)
- Blockers: 0

The phase's headline feature — looting a corpse/container via the `take` action and the
LootPanel — was driven end-to-end in the browser. Gold and an item transferred from a
killed creature to the player. The treasury variant (task 4) is lair-specific and not in
the default content; it is covered by integration `TestLairTreasury` (3 tests, green).

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page — Play/DM split | pass | Two cards, EN/RU toggle present |
| 1.2 | Load session in Play UI | pass | `/play/:sid` connects to an API-created session, "Connected" toast, dashboard renders |

### Auto-discovered scenarios (Phase 2: loot & containers)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Kill → corpse becomes lootable | new `is_lootable` + awareness surfacing | pass | After combat ends, corpse appears as a Loot holder in peaceful mode |
| LootPanel renders loot | new LootPanel (task 3 loot UI) | pass | Shows "50g" + "Health Potion" (tooltip "heals 2d4+2 HP"), "Take all" button |
| Take all → transfer | `take` action + `transfer_items` | pass | Player gold 1000 → 1050, Health Potion added to Bag (with USE), corpse shows "Empty", "Take all" disabled |
| Attack a dead target | take/awareness exposes corpses | pass | Graceful rejection: log shows "Цель 'xp_dummy' уже мертва."; no crash, no console errors |

### Combat + layout regression (exercises WS round loop / Fix A)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1/3.2 | Initiate combat + attack | pass | `combat_started`, dice breakdown `[d20(11)+4=15 vs КЗ 9], 3 урона (1d8 рубящий + +2 str)` |
| 3.4 | Combat ends | pass | `entity_died` → `Бой окончен`, sidebar returns to peaceful |
| 10.1 | Three-column dashboard | pass | Nearby / Character+Inventory / Location all visible |
| 3.5 (partial) | Level-up modal | pass | 500 XP auto-opened "Level up to L2" modal; deferred via Close, manual "Level up" button remained |
| WS disconnect | verify Fix A in-app | pass | "Exit session" returns to landing cleanly, no hang, backend logs clean |

## Findings

### Blockers
- None.

### Minor
- Dead creatures still render in the **Nearby** panel with Attack/Talk/Inspect buttons.
  Loot is correctly handled by the separate LootPanel, and attacking a corpse returns a
  graceful "already dead" message, so nothing breaks — but the Attack/Talk actions are
  meaningless on a corpse. Suggest hiding Attack/Talk for dead creatures in the Nearby
  panel (or omitting corpses from Nearby since LootPanel covers them). Filed as a polish
  item, non-blocking.

## Fixes landed during close-phase (before E2E)

These were found and fixed while running the integration suite, which had been failing
(the new lair tests had never run — `make check` excludes integration):

1. **Product — WS disconnect deadlock** (`adapters/api/routes_ws.py`). The async WS
   handler's `finally` called `remove_listener` → `stop_round` → `thread.join` directly on
   the event loop thread, while the round thread was blocked in `_send`
   (`run_coroutine_threadsafe(...).result()`) which needs that same loop. The loop froze
   for up to 5s (the join timeout) on every disconnect, freezing all sessions. Fixed by
   running `remove_listener` via `asyncio.to_thread`. Verified: a take→save/load→DELETE
   repro went from 5.02s to 7ms.
2. **Test — turn-stream off-by-one** (`tests/integration/test_lairs.py`). A turn-ending
   `take` auto-prompts the next turn; the helpers never drained it, so later
   `_advance_turn` reads were one turn behind (after movement, the player was at the wrong
   location and the treasury read as not-nearby). Added a `_take_treasury` helper that
   drains the re-prompt.

After both fixes: docker `make test-integration` → 149 passed; `make check` → 2228 backend
unit + 238 frontend, lint/typecheck clean.

## Log Analysis

- Only warning in the backend debug log was the intentional "already dead" attack test.
- No tracebacks, no `round_loop_error`, no `ws_send` failures on the happy path.
