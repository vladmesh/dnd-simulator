# E2E Report: Post-audit regression (Sprint 008)

**Date:** 2026-03-27
**Flags:** --no-llm
**Sections tested:** 1, 2, 3, 6 + auto-discovered
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 18 tested, 18 passed, 0 failed
- Quick fixes: 0 applied
- Blockers: 0 found

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Quick start — pick existing world | pass | World list shows library + forked worlds, character created, redirected to /play/:id, WS connected |
| 1.5 | Language toggle | pass | EN→RU switches all labels, world names, descriptions, buttons |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | NPC visible with Attack/Talk/Inspect buttons |
| 2.2 | Talk to NPC (rule-based) | pass | Player says text, NPC responds with canned reply |
| 2.3 | Wait and time advance | pass | Time 10:00 → 11:00 (1 hour) |
| 2.4 | Move between locations | pass | Moved to Market Square, new NPC + merchant visible, paths updated |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | Combat started, initiative order, battle map, first attack landed |
| 3.2 | Attack and damage | pass | d20+5 roll shown, damage applied, "wounded" status |
| 3.3 | End turn and NPC response | pass | NPC used Health Potion, round advanced |
| 3.4 | Combat ends | pass | Enemy killed, "Бой окончен", sidebar returned to peaceful |

### Section 6: Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Create session | pass | New session created with toast, appears in list |
| 6.2 | Spawn creature | pass | Monster spawned at market, visible in table |
| 6.3 | Edit creature HP | pass | HP changed to 25, reflected in table as 25/10 |
| 6.4 | Toggle brain type | pass | API fires ("Set Brain" toast), stays rule_based without LLM key — expected |
| 6.5 | Delete creature | pass | Confirm dialog, creature removed from table |
| 6.6 | Advance time | pass | 24h advanced, weather + squad events reported |
| 6.7 | Save and load | pass | Save created, load confirmed via dialog, state restored |

### Auto-discovered scenarios (Sprint 008 changes)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Landing page Player/DM split | Phase 5 restructure | pass | Two cards: Play + Dungeon Master |
| Fork world from master | Phase 5 fork UI | pass | Fork dialog, new world appears with Fork+Delete |
| Delete forked world | Phase 5 delete UI | pass | Confirm dialog, world removed |
| World editor stepper | Phase 4 master restructure | pass | 5 layer tabs, entity CRUD tables, Add/Edit/Delete per entity, Back/Next/Close navigation |

## Quick Fixes

None needed.

## Findings

### Blockers

None.

### Minor

None.

## Log Analysis

- No errors or exceptions in backend logs
- No browser console errors
- Only log entry of note: expected "target too far" action_failed when trying to attack from 45ft (correctly blocked)
- Many accumulated session log dirs in /tmp/dnd-e2e-logs/ from previous runs (cosmetic)
