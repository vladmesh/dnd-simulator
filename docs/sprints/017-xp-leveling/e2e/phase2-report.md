# Phase 2 E2E Report

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 2 — Level-up mechanics + Paladin L2 fix

## New Functionality Tested

Phase 2 is backend-only (level-up endpoint, level-aware features and pools, Action Surge). The level-up UI lands in Phase 3, so the new endpoint was exercised directly via REST against the live backend; the UI was used for regression only.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Fighter L1→L2 via `POST /api/player/sessions/{sid}/level-up` (XP patched to 300, current_hp=5/12) | level=2, max_hp=20 (+8 = d10 avg 6 + CON 2), current_hp=13 (delta added), `level_up_available=false`, new `action_surge` 1/1 pool, existing `second_wind` preserved, `xp_to_next_level=600` | exactly as expected | pass |
| Second consecutive level-up call when flag is False | HTTP 4xx with clear detail | HTTP 400 `{"detail":"No level-up available"}` | pass |
| Validation: ability key normalization (`str/dex/...` enum) | 400 on invalid key | 400 `'strength' is not a valid Ability` (sanity check) | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| List worlds (Master view) | pass | sword_vale + test_vale rendered |
| Create new session via Master tab | pass | session 7c6cb154 created |
| Create Fighter character via Play wizard (Defense FS) | pass | dashboard loaded, AC=19 (18 base + Defense +1) confirms FS pipeline still wires through |
| Basic combat (attack NPC `marta` with longsword) | pass | crit hit, `1d8 slash + 1d8 weapon_crit` for 4 dmg, target killed, combat auto-ended after kill |
| Reputation drop on kill | pass | "Your reputation with kingdom changed (50 → 30)" |
| WebSocket live updates | pass | combat log streamed in real time |

## Quick Fixes Applied

None.

## Log Analysis

- No ERROR or traceback entries in `/tmp/dnd-e2e-logs/serve.log` for the test session.
- Backend reload watcher behaved (no spurious reloads during E2E).
- Frontend dev server fell back to port 5177 (5173–5176 occupied by stale Vite instances from prior sessions); Vite proxy still routed `/api` correctly. Not a phase blocker.

## Blockers

None.

## Minor Issues

- Character creation REST schema uses `char_class` (snake-cased) and ability enum keys `str/dex/con/int/wis/cha`; full names like `strength`/`class_name` are rejected. Documented in OpenAPI but easy to trip over from manual curl. Not in scope to change.
- Many stale `session_*/` debug log directories accumulated in `/tmp/dnd-e2e-logs/`. Cosmetic.
