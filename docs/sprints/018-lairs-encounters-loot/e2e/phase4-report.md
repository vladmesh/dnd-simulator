# E2E Report: sprint018-phase4

**Date:** 2026-06-28
**Flags:** --no-llm
**Sections tested:** phase-4 feature (time-of-day encounters) + core regression (1, 2, 3, 13) on `test_vale`
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, backend :8001, frontend :5173

## Summary

- Scenarios: 9 tested, 9 passed, 0 failed
- Phase 4 feature (time-of-day gating): **PASS** — verified live (day empty / night spawn) on the running server
- Quick fixes: 0
- Blockers: 0

The phase deliverable is time-of-day encounter gating. The browser regression confirms the
modified `ActivationManager` path (encounter rolls on movement → activation → combat) still
works end to end. The feature itself was driven against the same live server through the real
HTTP/WS API (the Play UI can't set a start location, and movement advances the clock
unpredictably, so a controlled day-vs-night observation at a specific location isn't reachable
by clicking alone).

## Results

### Section 1: Session Setup (regression)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page Play/DM split | pass | Two cards + EN/RU toggle |
| 1.4 | Point buy | pass | Standard model; scores default to 10 (12 pts pre-spent → 15/27 remaining), STR + disabled at 15. Not a bug. |
| 1.5 | Class-specific UI | pass | Fighter → Fighting Style selector (Defense/Dueling/GWF); Chain Mail + Longsword + Shield |
| — | Character create | pass | Preview HP 12 (d10+CON2), AC 19 (16 mail +2 shield +1 Defense), Gold 1000. Created, redirected to dashboard. |

### Section 2: Peaceful Mode (regression)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | Dashboard three-column (Nearby/Character+Inventory/Location); barkeep in Nearby with Attack/Talk/Inspect |
| — | Header | pass | HP 12/12, location "The Dusty Flagon", time Y1490 M6 D1 10:00 |

### Section 3: Combat (regression)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | Attack barkeep (auto-hostility) → "Бой начался", initiative order, CombatPanel + BattleMap, action-budget bar |
| 3.2 | Attack and damage | pass | Hit: `[d20(8)+4=12 vs КЗ 10], 4 урона (1d8 рубящий + +2 str)`; full roll + damage breakdown |
| 3.4 | Combat ends | pass | "человек погибает" → "Бой окончен" → sidebar back to peaceful; Phase-2 Loot panel shows corpse (Take all disabled / Empty) |

### Section 13: Faction Relations (regression)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 13.2 | Kill reputation drop | pass | `Your reputation with militia changed (100 → 80)` (reputation_changed) |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Day/night encounter gating (night-only `night_hollow` table) | Phase 4 deliverable | **pass** | Live, deterministic: DAY (10:00) `night_hollow` spawns = `[]`; NIGHT (02:00, after `time/advance` 16h) spawns = `['Bandit']`. |
| Day/night signal read live | new `IS_DAYLIGHT` geography query | pass | Browser session at 10:00 logged `encounter_rolling ... is_day:true`; untagged crossroads region goblins still spawned (no regression). |
| Gating mechanism (logs) | confirm the rule fires | pass | Day: `encounter_roll_off_hours (template=bandit, time_of_day=night, is_day=true)` skips the entry. Night: `encounter_rolling ... is_day:false` → `encounter_spawn bandit`. |

## Quick Fixes

None. No in-scope bugs found.

## Findings

### Blockers
None.

### Minor (all pre-existing, not Phase 4)
- **Mixed EN/RU strings.** Game text is RU (combat log, race label "человек", "КЗ", damage types
  "дробящий"/"рубящий") while UI chrome is EN. Backend runs `DND_LANGUAGE=ru`. Already logged at
  the Phase 3 close.
- **Dead creature still shows Attack/Talk in Nearby.** Corpse keeps the Attack/Talk buttons after
  death (loot is handled by the Loot panel). Already logged at the Phase 2 close.
- **Combat→peaceful turn flush.** Right after a kill ends combat, clicking a Move path before
  pressing End Turn is rejected with `'wait' недоступно в бою` (phase still `combat`). Pressing
  End Turn first works. Benign; combat/turn code untouched this phase.
- **Master time-advance doesn't refresh the player WS header.** Advancing the clock via the master
  REST endpoint updates world time but doesn't push an update to a connected player client (header
  stayed 10:00). Expected for a master-side op; normal in-game time changes (Wait) do update.

## Log Analysis

- Zero tracebacks / exceptions / 500s across the whole run.
- Only `action_failed` entry is the benign `wait`-in-combat rejection above (info level).
- Phase 4 code path observed healthy live: `is_day` computed via the geography `IS_DAYLIGHT`
  query on every roll; `encounter_roll_off_hours` gates night entries by day; untagged entries
  roll in both phases.
