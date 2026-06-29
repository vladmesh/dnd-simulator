# E2E Report: sprint020-phase2

**Date:** 2026-06-29
**Flags:** --no-llm
**Sections tested:** Phase 2 lens projection (auto-discovered) + regression (1, 6, 3, 10)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 11 tested, 11 passed, 0 failed
- Quick fixes: 0
- Blockers: 0

Phase 2 is a projection-only three-lens cut over `/api/master/*`. Focus was the lens
behavior (worldbuilder / DM / admin / fallback), plus a core-flow regression to confirm
the `apiClient` world-fetch change and identity-header propagation didn't break the game.

## Results

### Auto-discovered scenarios (Phase 2 lens projection)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| L1 | Landing role selector | pass | name input + role select (worldbuilder/dm/admin/player), Play + Master cards, lang toggle. Identity persists to localStorage. |
| L2 | Worldbuilder lens | pass | identity line `alice · Создатель миров`; only own world (`Alice Realm`) shown — base/system worlds excluded (creator scoping works); **no Sessions tab**; Fork/Delete present (canWrite). |
| L3 | DM lens — sessions scoped | pass | identity `dana · Мастер`; Worlds + Sessions tabs; own session `915b92ed` shown, other DM's `4aac4936` filtered out; description surfaces attribution+clock (`— · Y1490 M6 D1 10:00 · sword_vale · dana`); write controls present. |
| L4 | Admin lens — worlds | pass | identity `admin1 · Админ`; **all 4 worlds** shown cross-creator; **no Fork/Delete** (writes stripped). |
| L5 | Admin lens — sessions | pass | all sessions visible incl. both dana + other_dm (no scoping); **no New Session, no delete-session, no world-select** (writes stripped); Manage present on every session. |
| L6 | Admin observe SessionView | pass | `Наблюдение (только чтение)` badge; tabs reduced to **World + Creatures only** (Time/Saves stripped); world tables read-only. |
| L7 | Admin observe Creatures + inline inventory | pass | no Actions column, no Spawn, names are plain spans (not edit buttons), brain type plain text (not toggle). **Inline items (Предметы col):** Edgar→equipped `warhammer smash`, Gretta→`Health Potion / Dagger / Flaming Longsword`, others→equipped weapons, Marta→`—`. Closes `master-panel-creature-inventory` remnant. |
| L8 | Fallback lens (player role) | pass | full god-mode: all worlds, Fork on all + Delete on editable, Sessions tab present. |

### Regression

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.2/1.4/1.5 | Play → world select → char creation | pass | all worlds listed (apiClient world-fetch intact); point-buy 15/27 for all-10s; preview HP 10 / AC 18 / Gold 1000; equipment Chain Mail+Longsword+Shield; Fighter fighting-style selector present. |
| 10.1 | Three-column dashboard | pass | Nearby (marta) / Character (Human Fighter L1, **AC 19** = Chain Mail 16 + Shield 2 + Defense 1, confirms fighting style) / Location (Солёный Якорь + paths). |
| 3.1/3.2/10.5/10.6 | Initiate combat | pass | `Бой начался! Порядок инициативы: Adventurer, Марта`; attack log fully RU-localized w/ dice breakdown `[d20(5)+2=7 vs КЗ 10], промах` (no placeholder leak); CombatPanel + BattleMap (@ / 1) render; budget bar Действия1/Бонус1/Движение30фт/Реакция1. |

## Quick Fixes

None.

## Findings

### Blockers
None.

### Minor
- **Projection-only world-scope quirk.** Worldbuilder/DM lenses scope worlds to `creator=userId`, so they see none of the base/system worlds. A DM with no own worlds gets an empty world list, which leaves "New Session" disabled (nothing to start a session from). This is inherent to the documented "creator = attribution, role not enforced yet" cut — worlds aren't shareable until the M2M/DB access sprint. Note for that future sprint, not a phase-2 defect.
- **WS StrictMode double-mount warning** (`WebSocket is closed before the connection is established`, wsClient.ts:31) — benign dev-mode double-connect; the socket reconnects and data is live. The WS URL now carries `user_id`/`role` query params (phase-1 identity propagation working). This evict-on-quick-disconnect is exactly what phase 3's `session-disconnect-debounce` targets.
- **Test detritus** — ~313 leftover saved sessions in `saves/` (and matching dirs in LOG_DIR) clutter the admin park view. Cosmetic; `make clean` clears them. Confirms admin "whole-park" listing works at scale.

## Log Analysis

- Only backend errors were two `RuntimeError: No manifest.yaml found in .../arena` 500s — both from the report author's data-seeding curl (arena is test-only content, absent from live `content/worlds/`), not from the app under test. The browser-driven game flow produced zero errors.
