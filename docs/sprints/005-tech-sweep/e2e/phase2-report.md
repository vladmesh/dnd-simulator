# Phase 2 E2E Report

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 2 — God Class Splits

## Scope

Phase 2 was a pure structural refactor — extracting AwarenessBuilder, ActivationManager, and QueryHandler from EntitiesLayer. No public API changes, no new features. E2E validates nothing broke.

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load home page, list worlds | pass | 4 worlds displayed correctly |
| Create character (Blood Arena) | pass | Human Fighter STR 16, redirected to /play/:id |
| Nearby entities panel | pass | 4 NPCs visible with Attack/Talk/Inspect buttons |
| Location panel | pass | "Кровавая Арена" with description |
| Character panel | pass | Stats, AC, gold, ability scores all correct |
| Inventory panel | pass | 6 equipment slots rendered |
| Initiate combat (Attack razor) | pass | Combat started, initiative rolled, battle map rendered |
| Attack resolves correctly | pass | [d20(14)+5=19 vs AC 13], 4 damage — format correct |
| NPCs act on their turns | pass | Equipped weapons, moved, attempted attacks |
| Combat UI | pass | Budget bar (actions, bonus, movement, reaction), enemy list with distances |

## Log Analysis

- 0 errors, 0 exceptions, 0 tracebacks in current session logs
- 0 console errors in browser
- Pre-existing blocked-move warnings from prior sessions (not a regression)

## Blockers

None.

## Minor Issues

None new. Pre-existing LLM NPC wall collision behavior noted in prior E2E report still present.
