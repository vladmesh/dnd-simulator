# E2E Report: sprint019-phase2

**Date:** 2026-06-29
**Flags:** --no-llm
**Sections tested:** 1 (char creation), 2 (peaceful), 3 (combat), 6 (master panel), + 10.1, 13.2/13.3
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 18 tested, 18 passed, 0 failed
- Quick fixes: 0
- Blockers: 0

Phase 2 was a behaviour-preserving refactor across three control-plane surfaces. E2E targeted
exactly those surfaces:
- **Task 1** (worldbuilder + content CRUD peel → `WorldBuilderCommands`) → Section 6 (worlds
  list, editor stepper, entity-edit read, fork, delete, sessions, spawn/brain/delete creature).
- **Task 2** (player commands peel → `PlayerCommands`: create_player / player_status) → Section 1
  (character creation) + the in-game character panel.
- **Task 3** (action-parsing seam in `routes_ws.py` + public World query API) → every WS action:
  talk / wait / attack-into-combat (Sections 2, 3).

Every surface works. All anomalies observed are pre-existing and already documented in the
phase-1 report (F1/F2/F3 below); none is a phase-2 regression. The fork→delete and
spawn→delete cycles left **zero** disk mutations (git tree clean, no leftover fork world).

## Results

### Section 1: Session Setup (player commands peel)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing Play/DM split | pass | Both cards + EN/RU toggle |
| 1.3 | Language toggle EN→RU | pass | All chrome labels switch to RU |
| 1.2 | Quick start — Sword Vale, Fighter | pass | Redirect to /play/:id, WS connected, first turn delivered |
| 1.4 | Point buy | pass | STR 15 → 9pts, + disabled at 15; CON 14; "Осталось 3/27"; preview HP 12 / AC 19 (Chain Mail 16 + Shield 2 + Defense 1) / Gold 1000 — all exact |
| 1.5 | Class-specific UI (Fighting Style selector) | pass | Defense selectable; starting equipment Chain Mail/Longsword/Shield |
| — | Created character round-trip (`create_player`→`player_status`) | pass | Human Fighter L1, HP 12/12, AC 19, 1000g, STR 15/ВЫН 14 — matches creation inputs exactly |

### Section 2: Peaceful Mode (action-parsing seam)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | marta visible with Attack/Talk/Inspect |
| 2.2 | Talk to NPC (rule-based) | pass | `talk` (target+text) parsed via seam: "Ты говоришь…" → "человек говорит: «Что будете заказывать?»" |
| 2.3 | Wait / time advance | pass | `wait` (paramless) via seam: 10:00 → 11:00 |

### Section 3: Combat (attack action via seam)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | "Бой начался! Порядок инициативы: Марта, Adventurer" |
| 3.2 | Attack and damage | pass | nat-20 crit, full breakdown `[d20(20)+4=24 vs КЗ 10]`, 4 dmg (1d8 + 1d8 weapon_crit + +2 str) |
| 3.4 | Combat ends | pass | "человек погибает" → "Бой окончен." |

### Section 6: Master Panel (worldbuilder + creature command peel)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Worlds tab | pass | Полигон Level-up editable (Fork+Delete); Долина Мечей / Тестовая Долина library (Fork) |
| 6.2 | Fork world | pass | New ID → toast "Мир форкнут.", new editable world appears |
| 6.3 | Delete world | pass | RU confirm → toast "Мир удалён.", no disk leftover |
| 6.4 | World editor stepper | pass | 5 tabs, regions/locations/npcs tables w/ Add/Edit/Delete, Back/Next/Close |
| — | Entity edit-read (peeled CRUD read) | pass | xp_dummy form fully populated from YAML (HP 3, AC 8, STR 8, combat pos 15,10, xp 500). Cancelled w/o save |
| 6.5 | Sessions tab + New Session | pass | World picker, id field, session list, Управление links |
| 6.6 | Spawn creature | pass | Test Goblin spawned (10/10, arena_floor) after valid role; see F1 |
| 6.8 | Toggle brain type | pass | PUT .../brain → 200 OK; stays rule_based via `llm_not_configured_fallback` (no API key in dev stack) |
| 6.9 | Delete creature | pass | Test Goblin removed via session command |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| 10.1 Three-column dashboard | regression baseline | pass | Nearby / Character+Inventory / Location all visible |
| 13.2 Kill reputation drop | attack path | pass | "Your reputation with kingdom changed (100 → 80)" (English — see F2) |
| 13.3 Auto-hostility | attack peaceful NPC | pass | Attacking marta auto-started combat with correct sides |
| `get_world_state` via master SessionView | WorldStateCommands surface | pass | regions/nations/settlements render correct RU data |

## Quick Fixes

- None.

## Findings

### Blockers
- None.

### Minor (all pre-existing, none from phase 2)

- **F1 — Spawn-creature Role is free-text but backend requires the `NpcRole` enum.**
  Empty Role → HTTP 400 with a raw Pydantic message in the dialog
  (`Input should be 'commoner', 'blacksmith', …`). Works with a valid value (`guard`).
  Same as phase-1 F1; backlog `spawn-role-freetext-enum`; candidate for phase-3 visible-gaps.
  Hand-built `CreatureForm`, unrelated to the phase-2 command peel.

- **F2 — Mixed UI language.** Frontend i18n defaults EN; backend `DND_LANGUAGE` defaults `ru`.
  With the UI set to RU, the inverse of phase-1 F2 shows: backend-built combat-log fragments
  leak English into an otherwise-RU log — "You attack", "longsword slash", "weapon_crit",
  "+2 str", and "Your reputation with kingdom changed (100 → 80)". This is exactly the
  `combat-log-i18n-gaps` item the phase-3 plan targets. Pre-existing, not a phase-2 regression.

- **F3 — Dev-only WS race on first turn.** One `listener_error` on `WsEventListener.on_turn`
  at the very first turn (React StrictMode dev double-mount: first socket torn down +
  reconnected). The session listener dispatch correctly isolated it — the game continued and
  every later turn delivered. No production occurrence (no StrictMode double-mount). Same as
  phase-1 F3; it re-exercises the listener-error isolation that phase-2's public-query seam
  preserved.

- **F4 (new, cosmetic) — Dead NPC keeps Attack/Talk buttons in the Nearby panel.** After
  marta died, her card still showed Атаковать / Говорить. This is the backlog
  `corpse-nearby-actions` item already slated for phase 3. Not a phase-2 regression.

- **F5 (new, cosmetic) — Creature-delete toast reads just "Удалить"** (imperative verb) vs the
  world-delete's proper sentence "Мир удалён." Frontend string only, unrelated to the backend
  peel. Trivial.

## Log Analysis

Full backend-log error sweep for the run: exactly two error/4xx events, both accounted for —
one 400 (F1 empty-role spawn, reproduced then succeeded with a valid role) and one
`listener_error` (F3). **No 500s, no Internal Server Errors, no tracebacks, no other
error-level events.** The peeled `WorldBuilderCommands` / `PlayerCommands` mixins and the
`service/action_parsing.py` seam all behaved identically to pre-refactor: behaviour preserved.
