# E2E Report: sprint018-phase3

**Date:** 2026-06-28
**Flags:** --no-llm
**Sections tested:** 1, 2, 3 (+ 4.2, 9.1, 10.x, 13.3 observed in passing)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, world: Sword Vale

## Scope rationale

Phase 3 (region encounter tables) is a backend-only change: encounter tables now
resolve region → location at load time in `GameService`, collapsing into the flat
per-location map the runtime already consumes. There is no new UI surface. The
region-fallthrough / override behavior is deterministically verified by the new
integration tests (`tests/integration/test_encounters.py`, 3 tests against the
live stack) and in-process product tests (`tests/unit/test_region_encounters.py`,
4 tests). So E2E here is a regression on the shared path that change feeds: the
activation/round loop and the encounter-check that fires on location change —
mirroring the phase-1 E2E approach.

## Summary

- Scenarios: 12 tested, 12 passed, 0 failed
- Quick fixes: 0
- Blockers: 0

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing — Play/DM split | pass | Two cards, EN/RU toggle present |
| 1.2 | Quick start — create fighter, enter game | pass | Sword Vale → New Session → Fighter, redirect to /play/:id, WS connected, first turn |
| 1.4 | Point buy | pass | Counter consistent (10 costs 2 → 15/27 at all-10s); STR + disabled at cap 15; preview HP 10/AC 18/Gold 1000 |
| 1.5 | Class-specific UI | pass | Fighter shows Fighting Style selector; equipment Chain Mail + Longsword + Shield |
| 4.2 | Fighting Style (Defense) AC | pass | Selecting Defense: preview AC 18 → 19 (Chain Mail 16 + Shield 2 + Defense 1); HP 10 → 12 at CON 14 |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.3 | Wait — time advance | pass | 10:00 → 11:00, banner updates; round/activation pass ran clean |
| 2.4 | Move between locations | pass | Salty Anchor → Market Square; Location panel + paths update; **activation/encounter-check fired on the location change with no error** (the path phase 3 feeds) |
| 9.1 | Trade panel visible | pass | Gretta the Merchant auto-shows Buy list (Health Potion 50g, Dagger 200g, Flaming Longsword 500g) on arrival |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | Attack NPC → "Бой начался! Порядок инициативы: Gretta the Merchant, Adventurer"; sidebar → Combat panel, Round 1 |
| 3.2 | Attack and damage | pass | `[d20(10)+4=14 vs КЗ 10], 5 урона (1d8 рубящий + +2 str)` — full breakdown, correct STR bonus |
| 3.3 | End turn + NPC response | pass | NPC equips Dagger, moves NE, attacks vs AC 19 (miss); End Turn → Round 2, NPC turn resolves |
| 13.3 | Auto-hostility | pass | Attacking a peaceful merchant outside combat started combat with correct sides; HOSTILE scope did not block the opening attack |
| 10.5 / 10.6 | Combat layout + budget bar | pass | BattleMap replaces Location panel (@ + enemy marker); budget shows Actions 1 / Bonus 1 / Movement 30ft / Reaction 1 |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Location-change activation/encounter path | phase 3 feeds `effective_encounters` into this path | pass | Move to a new location ran the activation pass + `_check_encounters` with no crash/error; location updated cleanly |
| Test Vale loads in world picker | phase 3 edited `content/worlds/test_vale` (region_encounters + new `forest_edge` location) | pass | Test Vale listed and selectable; no load error |

## Quick Fixes

- None.

## Findings

### Blockers
- None.

### Minor
- **Mixed EN/RU in game-event strings (pre-existing, unrelated to phase 3).** With UI language EN, perceived race renders as "человек" and combat-log verbs are RU ("экипирует", "перемещается", "промах", "урона", "рубящий", "Бой начался!"), while UI chrome and template fragments ("You attack", "attacks you", "Round") are EN. This is the established split: backend game strings follow `DND_LANGUAGE` (ru default), the frontend toggle controls only UI chrome. Not introduced by this phase; logged here for completeness.

## Log Analysis

- Backend log: 0 errors / exceptions / tracebacks across the session.
- Structured logs (`session_14db0abd`): no error/warning entries beyond expected `action_failed` gameplay warnings (none hit this run).
- Browser console: 0 errors, 1 warning — a benign WebSocket reconnect race on initial connect (`wsClient.ts:30`, React StrictMode double-mount in dev). Pre-existing, not a regression.
