# E2E Report: sprint019-phase3

**Date:** 2026-06-29
**Flags:** --no-llm
**Sections tested:** 2 (Perception), 3 (Combat), 15 (Encounters) — targeted at Phase 3 changes
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 6 tested, 6 passed, 0 failed
- Quick fixes: 0
- Blockers: 0 (no NEW blockers)

Phase 3 shipped three visible fixes: combat-log i18n (movement errors `_()`-wrapped + attack-line catalog drift), encounter-spawned perceiver, and a frontend gate hiding Attack/Talk on lootable nearby entities. All three confirmed working in the live UI under a Russian session.

## Results

### Section 3: Combat (combat-log i18n)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat (RU log) | pass | "Бой начался! Порядок инициативы: Марта, Adventurer" — RU |
| 3.2 | Attack line localizes (catalog drift fix) | pass | "Ты атакуешь человек (longsword slash) [d20(13)+2=15 vs КЗ 10], 4 урона (1d8 рубящий)" — renders RU, **no `{oa}`/`{weapon}` placeholder leak**, КЗ=AC, рубящий=slashing. This is exactly the catalog-drift bug the task fixed. |
| 3.4 | Combat ends (RU log) | pass | "человек погибает", reputation line "Твоя репутация с kingdom изменилась (100 → 80)", "Бой окончен." all RU |

Movement-handler errors (`rules/handlers/movement.py`, 9 strings wrapped in `_()`, em-dashes dropped) were not force-triggered through the battle map (they need an in-combat invalid click-to-move). They are covered by the 2 new unit tests (blocked-move RU + EN regression), and the RU `.mo` catalog is proven to load live across three independent string groups (attack/reputation/combat lifecycle + encounter flavor), so the same `_()` + `.mo` path is exercised. Verified-by-unit + live-catalog-proof; not separately driven in UI.

### Section 2: Perception (corpse-nearby-actions)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1a | Living entity shows Attack/Talk | pass | Before death, marta (человек) showed Атаковать + Говорить + Inspect (3 buttons) — regression guard for the living |
| 2.1b | Corpse hides Attack/Talk | pass | After killing marta, the Nearby panel shows the corpse with **only the Inspect button** (no Атаковать/Говорить). Looting routed through the separate "Добыча" panel ("Забрать всё"). |

### Section 15: Encounters (encounter-spawned perceiver)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 15.3 | Region encounter spawns + perceiver flavor | pass | test_vale crossroads region table (goblin 0.4) rolled on session start; log shows **"Поблизости что-то шевелится"** (RU flavor of `_("Something stirs nearby")`), NOT the fallback "Something happened (encounter_spawned)", and **does not leak the monster roster** (no "Гоблин" in the log line) per world-does-not-adapt-to-player. A goblin spawned and appears in the Nearby panel, confirming a real encounter fired. |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| RU attack/reputation/combat-lifecycle log rendering | commit d3a2193 (catalog regen + i18n) | pass | All combat-log strings render RU; placeholder leak gone |
| Corpse loot panel coexists with hidden actions | commit 17d2fb6 | pass | "Добыча" / "Забрать всё" present on corpse while Attack/Talk hidden |
| Encounter perceiver flavor, no fallback, no name leak | commit d3a2193 | pass | Confirmed in UI log + backend logs (5 `encounter_spawn` events, 0 "Something happened") |

## Quick Fixes

None.

## Findings

### Blockers
None.

### Minor (all pre-existing, not Phase 3 regressions)
- **Dev-only WebSocket StrictMode race** — frontend console warning "WebSocket is closed before the connection is established" on session entry. Documented in phase1/phase2 reports; React StrictMode double-mount in dev only, no functional impact.
- **Item/faction names render in English** — starting equipment ("Chain Mail, Longsword, Shield"), weapon attack label ("longsword slash"), and faction id ("kingdom") show English inside otherwise-RU lines. Pre-existing content/catalog i18n gap, explicitly out of Phase 3 scope (the task scoped i18n to `movement.py` + the attack-line catalog drift only). Candidate for a future i18n sweep.
- **`_perceive_take` (loot) strings untranslated** — noted by the task author as out of scope; not surfaced in these scenarios (corpse had empty inventory).

## Log Analysis

- Backend (`/tmp/dnd-e2e-backend.log`): multiple `encounter_rolling` / `encounter_spawn` events (goblin_1..goblin_5 across crossroads locations); **zero** "Something happened" fallback; **zero** errors/exceptions/tracebacks; no 500/unhandled/AssertionError.
- Frontend console: 0 errors, 1 warning (the dev-only WS StrictMode race above).
