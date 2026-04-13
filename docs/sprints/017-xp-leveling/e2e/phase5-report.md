# Phase 5 E2E Report

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 5 — Post-audit cleanup

## New Functionality Tested

Phase 5 was pure refactor (purity, unit tests, GameService method, `Any` cleanup) — no user-visible surface changes. E2E focuses on verifying the refactored `GameService.level_up_player` / `GameService.player_status` path still produces the same user-visible outcome.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Create Fighter L1 (Level-up Test Arena) | HP 12, AC 19, shows 3 nearby dummies | HP 12/12, AC 19, `xp_dummy` + `practice_thug` listed | pass |
| Attack `xp_dummy` (1 HP) with longsword | hit → kill → `xp_gained` log entry → Level up button appears | Crit (d20=20+4=24 vs AC 9), 3 dmg, dummy dies, `xp_gained` event in combat log, "Level up" button visible on Character panel | pass |
| Click Level up → Confirm in modal | L1→L2, max HP 12→20 (+8), Action Surge pool unlocked (1/short rest) | `Human Fighter L2`, HP now `20/20`, resource badge count increased to 3 (includes Action Surge). No console errors. | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load `/play` world list | pass | Three worlds rendered; `Level-up Test Arena` card present |
| Character creation point-buy + preview | pass | STR 15 / DEX 13 / CON 14 configured; Preview HP 12, AC 19 match post-creation state |
| Battle map render on combat start | pass | 6x6 grid drawn, `@` (player) and `1` (dummy) glyphs positioned; combat sidebar shows Round 1 |
| Combat log i18n | pass | Russian event text ("Бой начался!", "погибает") renders alongside English attack log |

## Quick Fixes Applied

- **`src/dnd_simulator/rules/combat.py::roll_initiative`** and **`src/dnd_simulator/core/combat.py::BattleMap.place_randomly`**: both fell back to `random.Random()` (fresh unseeded RNG) when no `rng` was passed, bypassing `DND_DICE_SEED`. Switched the fallback to `get_global_rng()` so initiative + initial placement respect the seeded module RNG. This eliminated a long-standing integration-suite flake in `tests/integration/test_player_state_xp.py::TestPlayerStateXpAfterKill::test_rest_status_updated_after_kill` — initiative ordering (and, depending on placement, reach) was non-deterministic across runs, occasionally shifting the RNG stream so the player's seeded attack roll landed on a miss or `target_dummy` was scattered outside reach. No test changes were needed after the fix; 142/142 integration tests now pass deterministically.

## Log Analysis

- `/tmp/dnd-e2e-logs/session_65d318b9/full.jsonl`: clean. No `ERROR`, no `Traceback`, no `ws_send_failed`. `xp_gained`, `reputation_changed`, `combat_started`, `entity_died` all emitted as expected.
- Russian log text like `"Что-то произошло (xp_gained)"` indicates the `xp_gained` event type lacks an i18n message template on the client combat-log renderer. Not a phase-5 regression (the event was added in phase 1 and uses the same fallback path); noted as a minor cosmetic gap.

## Blockers

None.

## Minor Issues

- Combat log renders `xp_gained` via a generic "something happened" fallback (`"Что-то произошло (xp_gained)"`) — pre-existing, not introduced by phase 5. Candidate for backlog: add a proper client-side i18n message for the `xp_gained` event.
