## Phase 4 E2E Report

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 4 — E2E follow-up bug sweep

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Load arena with per-location battle map (task 3) | 5-cell square rendered | 5x5 grid, player `@` visible at correct cell, NPC `1` at (4,2) | pass |
| Enter combat, resolve attack (task 2 coord convention) | No out-of-bounds errors | Attack resolved, Dueling fighting-style bonus (+2) applied, XP Dummy dropped to 0 HP | pass |
| Combat sidebar HP/AC consistency (task 4) | Sidebar = top-bar = 20/20 | Both read 20/20 live; no stale numbers after Dueling-damage volley | pass |
| Attack submenu a11y (task 6) | `role=menu`, menuitems disambiguated | anchor `aria-haspopup=menu` `aria-expanded=true`; items `Attack practice_thug`, `Attack practice_thug + Smite (slot 1)(1/2)` | pass |
| RuleBrain flee invariant (task 1) | No unprovoked flee from xp_dummy | Thug/dummy held ground; faction_hostility_check stayed NEUTRAL until attack | pass |
| Level-up Cancel defer contract (task 5) | Validated at vitest level | Covered by phase3-task3 + phase4-task5 vitest (238 frontend tests green); not re-driven here — requires multi-round XP accrual which the saved session has no budget for | partial |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load worlds list | pass | All 3 worlds render |
| Character creation (Fighter, point-buy) | pass | STR 15 / CON 14 / DEX 12, HP 12, AC 19 preview correct |
| Join existing saved session | pass | `f89d546c` loads, Paladin L2, AC 18 (chain+shield+Defense FS from sprint-2) |
| Attack + combat start | pass | Combat sides, initiative, battle map, reputation drop, XP emission all wired |

## Quick Fixes Applied

**Blocker uncovered during E2E → fixed on the spot.**
- Attacking from saved session crashed the round loop: `ValueError: Position (15, 10) out of bounds for xp_dummy on 5x5 map`.
- Root cause: unit confusion in phase-4 task 3 content change. `BattleMap.width/height` are in **feet** (docstring pins this), but `level_up_test/arena_floor.battle_map` was authored `{width: 5, height: 5}` — interpreted as a 5 ft × 5 ft map (= 1×1 cell), so the 25-ft NPC coords fell out of bounds. Task 2 validator rejected non-5-multiple coords but didn't reach the map itself.
- Fix:
  1. `content/worlds/level_up_test/geography/locations.yaml`: 5→25 width/height (5 cells × 5 ft = 25 ft, matches the "5x5" description text).
  2. `content_loader/schemas.py::BattleMapContent`: tightened `ge=10 le=500` plus new `@field_validator` requiring width/height be a multiple of 5. Catches the same mistake at content-load time (fail-fast, mirroring task 2's combat_position validator).
  3. Updated two stale integration-test worlds (`reputation_test`, `sneak_test`) that carried the same 3-feet map error and would have crashed once the new validator landed: `width: 3 → 15`.
  4. Added `test_width_not_multiple_of_five_rejected` plus updated existing BattleMap parser tests to reflect feet semantics.
- Result: integration suite 142/142 green; E2E combat cycle (attack → kill → reputation drop → XP) runs end-to-end.

## Log Analysis

- `/tmp/dnd-e2e-logs/session_f89d546c/full.jsonl`: clean combat cycle post-fix. `round_loop_error` traceback disappeared; `combat_started`, `awareness_nearby`, `reputation_changed`, `xp_gained` all present. `ws_send_failed (debug)` appears once at each React StrictMode dev double-mount — harmless.
- No unhandled exceptions after the battle-map fix.

## Blockers

_(none remaining)_

## Minor Issues

- Dev-mode React StrictMode double-mounts WebSocket client → ephemeral sessions without a save get `session_empty_evict`d in ~4 ms; saved sessions re-hydrate fine. Not introduced by phase 4 and not user-visible in prod builds, but noisy and makes fresh-character E2E fragile. → backlog candidate: either debounce the WS cleanup on the client or suppress eviction when a reconnect arrives within a short grace window.
- `GAME OVER` banner fires whenever the round thread exits, even when the player is alive and just between rounds. Misleading UX. Not phase-4 scope, predates this sprint. → backlog candidate: rename event to `round_thread_exit` and only surface a banner when the player is actually unconscious/dead.
