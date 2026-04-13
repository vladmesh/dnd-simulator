# Phase 3 E2E Report

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 3 — Level-up UI + E2E

## New Functionality Tested

Phase 3 delivered the React level-up modal, dashboard wiring, and a dedicated arena world. All assertions for the primary scenario landed in the per-task report — see `docs/e2e-reports/017-phase3-level-up-2026-04-13.md` for the full Paladin L1→L2 walk-through (modal title, fighting-style dropdown, Confirm gating, level/HP/spell-slot deltas, Dueling +2 + Divine Smite damage breakdown, slot decrement). This file summarizes the close-phase verification on top of that.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Worlds list (post-changes) | `level_up_test`, `sword_vale`, `test_vale` all rendered with New Session buttons | three buttons present | pass |
| Backend reload after schema change | `make serve` accepts requests after `NpcContent.xp_value` field added | `/api/master/worlds` 200 OK | pass |
| Full level-up cycle (re-verified during task 3 implementation) | Paladin L1 kills xp_dummy → modal → Dueling → L2 → Smite kill on practice_thug | All assertions pass (see task report) | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Worlds API | pass | `/api/master/worlds` returns three editable + library entries |
| /play landing | pass | three world cards rendered via React |
| Integration suite | pass | 142 passed (one rerun after a flaky cleanup-DELETE timeout, see Quick Fixes) |

## Quick Fixes Applied

- `tests/integration/test_player_state_xp.py`: bumped the cleanup `requests.delete(..., timeout=5)` to `timeout=10` (matching the rest of the file). The first integration run hit a 5 s read timeout on the session DELETE in the finally block of `test_rest_status_updated_after_kill`; the rerun passed cleanly. Outlier 5 s value was almost certainly a copy-paste, not a deliberate threshold — every other call in the same file uses 10. Pre-existing, surfaced now under heavier session teardown.

## Log Analysis

- `/tmp/integration.log` first run — only the one cleanup timeout. Backend never logged a `DELETE … 200 OK` for that session id, consistent with the read timing out before the response landed (test had a long WS attack loop just before, which can leave background round/save work in flight).
- `/tmp/integration2.log` rerun — all 142 tests passed in 64.5 s, no warnings.
- `/tmp/dnd-e2e-logs/serve.log` (kept from the live E2E in task 3) — no ERROR or traceback; reload watcher behaved.

## Blockers

None.

## Minor Issues

- Combat sidebar `PlayerStats` panel keeps stale HP (pre-level value) until next round; top header HP bar is correct. Cosmetic — already noted in the task-level report.
- Default battle map size (~13×13) is much bigger than the 3×3 conceptual arena described in the task. Doesn't break the scenario but the map looks empty around the player. Candidate backlog item if/when battle-map sizing per location is parameterized.
