# Phase 1 E2E Report

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 1 — Pydantic Content Models + Parser Rewrite

## New Functionality Tested

Phase 1 was an internal refactoring (parsers rewritten to use Pydantic models). No new user-visible features. Testing focused on verifying existing functionality is unbroken.

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Main page loads, worlds listed | pass | Sword Vale and Test Vale displayed correctly |
| Create session (Sword Vale) | pass | Character creation form renders with all fields |
| Create character, enter game | pass | Player spawned at The Salty Anchor, NPC visible |
| Location info + paths | pass | Paths to Market Square and Docks shown |
| Initiate combat (attack NPC) | pass | Combat started, initiative rolled, battle map rendered |
| Move toward target | pass | Movement budget decremented correctly (30 -> 25 -> 20 -> 15) |
| Attack in melee range | pass | Roll displayed, action consumed, miss reported correctly |
| End turn, NPC responds | pass | Round advanced to 2, budget reset |
| Exit session | pass | Clean return to main page |

## Quick Fixes Applied

- **SpawnCreatureRequest empty string defaults:** `role`, `personality`, `settlement_id` had `str = ""` defaults. After Pydantic rewrite, `NpcContent` validates `role` as `NpcRole` enum — empty string fails validation. Changed to `str | None = None` so `exclude_none=True` drops them and `NpcContent` uses its own defaults.
- **Spawn endpoint error handling:** Added `RuntimeError` to the catch clause in the spawn endpoint. Location validation raises `RuntimeError` but the handler only caught `ValueError`/`KeyError`, causing 500 instead of 400.

## Log Analysis

- Session `dfeda494` (this E2E): no errors or warnings in session log.
- Pre-existing: a previous E2E session (`d9f70020`) had a spawn with invalid location `salty_anchor` — this triggered the RuntimeError→500 bug that was fixed above.

## Blockers

None.

## Minor Issues

None.
