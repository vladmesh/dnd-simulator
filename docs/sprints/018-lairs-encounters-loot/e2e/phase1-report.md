# E2E Report: sprint018-phase1

**Date:** 2026-06-28
**Flags:** --no-llm
**Sections tested:** 1, 2, 3 (+ spot checks: 8.1, 10.1/10.5/10.6, 13.2)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Scope rationale

Phase 1 (Lairs) is backend ecology: lair model, materialization, respawn, and
depletion on the EcologyLayer + activation_manager. There is no dedicated lair
UI, and no lair-bearing world ships in the frontend content, so the lair state
machine itself is covered by integration tests (`tests/integration/test_lairs.py`,
4 new tests). The phase did, however, touch the shared activation /
materialization / round path that every world drives. This E2E exercises that
path end-to-end through the real UI (session → peaceful → combat) to confirm no
regression.

## Summary

- Scenarios: 12 tested, 12 passed, 0 failed
- Quick fixes: 0
- Blockers: 0

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page — Play/DM split | pass | Both cards + EN/RU toggle render |
| 1.2 | Quick start — Sword Vale session | pass | Session created, WS connected ("Connected" toast), first turn delivered |
| 1.4 | Character creation — point buy | pass | STR 15 → +2 mod, `+` disabled at cap, remaining counter 27→8→3; preview HP 12 (CON 14), AC 19 (Chain Mail 16 + Shield 2 + Defense 1), Gold 1000 |
| 1.5 | Character creation — class-specific UI | pass | Fighter shows Fighting Style selector (Defense/Dueling/GWF); equipment = Chain Mail, Longsword, Shield |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | NPC "marta" visible with Attack/Talk/Inspect |
| 2.3 | Wait and time advance | pass | Time advanced 10:00 → 11:00 |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | "Бой начался! Порядок инициативы: Adventurer, Marta"; sidebar → CombatPanel, BattleMap appears, Round 1 |
| 3.2 | Attack and damage | pass | `d20(17)+4=21 vs КЗ 10, 3 урона (1d8 + +2 str)` — +4 = STR +2 + prof +2; out-of-reach attack correctly rejected ("Цель слишком далеко, 20 ft / 5 ft") without consuming the action |
| 3.3 | End turn and NPC response | pass | "Marta moved (10 ft)" then `человек attacks you (кулаки) [d20(5)+2=7 vs КЗ 19], промах`; Round 2 began |
| 3.4 | Combat ends | pass | Killing blow → `человек погибает` → `Бой окончен`; sidebar returns to peaceful (Nearby "Nobody around.", LocationPanel back) |

### Spot checks (touched by the same round/awareness path)

| Scenario | Status | Notes |
|----------|--------|-------|
| 8.1 View inventory panel | pass | 6 slots (Weapon/Armor/Shield/Head/Feet/Ring) + gold; Longsword/Chain Mail/Shield equipped |
| 10.1 Three-column dashboard | pass | Nearby / Character+Inventory / Location all visible |
| 10.5 Combat layout switch | pass | Right column → BattleMap during combat (`@` player, `1` enemy), reverts to LocationPanel after |
| 10.6 Action bar budget | pass | Actions/Bonus/Movement/Reaction shown with values |
| 13.2 Kill reputation drop | pass | `Your reputation with kingdom changed (100 → 80)` on kill |

## Findings

### Blockers
- None.

### Minor
- NPC race label renders in Russian ("человек") while the UI chrome and
  location free-text are English. Session content language defaults to the
  backend's `DND_LANGUAGE=ru` regardless of the frontend EN/RU toggle (gettext
  enum strings localize to ru; YAML free text stays as authored). Pre-existing,
  unrelated to phase 1. Not tracked here.

## Log Analysis

- Backend (`/tmp/dnd-e2e-backend.log`): no exceptions/tracebacks. The only
  `error` field is the intentional reach-validation `action_failed` (info level)
  triggered in 3.2.
- Browser console: 0 errors, 1 warning — a benign WS reconnect-timing warning
  ("WebSocket is closed before the connection is established") from Vite dev
  HMR / StrictMode double-mount. Not a defect.
