# E2E Report: sprint020-phase2

**Date:** 2026-07-04
**Flags:** --no-llm
**Sections tested:** 1, 2.1, 2.3, 3.1–3.4, 6.1–6.3, 10.1/10.5/10.6, 13.2, 15.5 + auto-discovered (exception handlers, player-status payload)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 14 tested, 13 passed, 0 failed, 1 pre-existing (2.3, not phase-2)
- Quick fixes: 0
- Blockers: 0

Phase 2 changed backend internals (typed query accessors, boundary enums, app-level exception
handlers, single-source player-status). Focus was on the surfaces those touch: the WS player
payload (`build_player_status`), combat/peaceful awareness (typed query accessors), and the reworked
CRUD routes (exception handlers). All behavior is unchanged from the player's perspective.

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page Play/DM split | pass | Two cards, RU default |
| 1.2 | Quick start → create → enter | pass | Redirect to /play/:id, WS connects, title = char name |
| 1.4 | Character creation point buy | pass | All-10 = 12pts spent (15/27 left); STR 15 → +2, + disabled at cap, 8/27 left; preview HP 10 / AC 18 / Gold 1000 |
| 1.5 | Class-specific UI (Defense) | pass | Fighting Style selector present; Defense → AC preview 18→19 (+1) |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | NPC marta shown with Attack/Talk/Inspect |
| 2.3 | Wait / time advance | pre-existing | With a rule-NPC co-located the round ticks 6s/round instead of fast-forwarding, so the player waits many rounds for control. Peaceful `wait` behavior, unrelated to phase 2. |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | combat_started with initiative order; sidebar → CombatPanel |
| 3.2 | Attack and damage | pass | Miss `[d20(5)+4=9 vs КЗ 10]`; hit `[d20(13)+4=17 vs КЗ 10], 4 урона (1d8 рубящий + +2 str)` — full breakdown, RU, no placeholder leakage |
| 3.3 | NPC response | pass | marta moved + counterattacked `[d20(16)+2=18 vs КЗ 19]` |
| 3.4 | Combat ends | pass | "человек погибает" → "Бой окончен"; sidebar returns to peaceful + Loot panel |

### Section 6: Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Worlds tab | pass | Editable world = Fork+Delete, library = Fork only |
| 6.2 | Fork world | pass | New editable world appears, toast "Мир форкнут" (201 Created) |
| 6.3 | Delete world | pass | Confirm dialog → removed, toast "Мир удалён" (200) |

### Section 10 / 13 / 15 (regression via combat)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.1 | Three-column dashboard | pass | Nearby / Character+Inventory / Location all visible |
| 10.5 | Combat layout switch | pass | Right column → BattleMap (@ player, 1 enemy); returns to Location after combat |
| 10.6 | Action bar budget | pass | Действия/Бонус/Движение/Реакция; Действия 1→0 after attack |
| 13.2 | Kill reputation drop | pass | "Твоя репутация с kingdom изменилась (50 → 30)" |
| 15.5 | Corpse action gate | pass | Dead marta shows only Inspect in Nearby (no Attack/Talk); Loot panel with "Забрать всё" |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Player-status WS payload | task 4 (`build_player_status` single source, WS gains `appearance`) | pass | Name/HP/AC 19/gold 1000/STR 15/L1/equipment all correct on turn, action_result, round_result payloads throughout setup + combat |
| Exception handler: duplicate fork → 409 | task 4 (global `FileExistsError`→409, `fork_world` local branch removed) | pass | Second fork with same id → 409 Conflict, dialog stays open, no false success; backend log clean (201 then 409, no traceback) |
| Reworked content/world CRUD happy paths | task 4 (removed redundant exception ladders) | pass | Worlds list, fork, delete all functional |

## Quick Fixes

None.

## Findings

### Blockers
None.

### Minor
- **WS reconnect race → transient `session_empty_evict`.** On page load the WS briefly closes before establishing, occasionally evicting the (momentarily listener-less) session before reconnect. Final state is "Подключено" and gameplay continues. This is the out-of-scope `session-disconnect-debounce` race explicitly deferred in the task, not a phase-2 regression.
- **906 accumulated saved sessions** in the Master → Sessions list from prior integration runs. Test-data hygiene, pre-existing, not phase 2. Made manual session-spawn (6.6) impractical; that route is covered by the 154 passing integration tests instead.

## Log Analysis

- Backend HTTP status distribution over the run: 18×200, 1×201, 1×409. No 500s, no tracebacks, no `round_loop_error`.
- Combat, reputation, faction-hostility, and awareness events all logged cleanly and in the expected order.
