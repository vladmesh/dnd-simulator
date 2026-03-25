# Sprint 004 Status

**Sprint:** 004-monster-encounters → 004-living-world (replanned)
**Phase:** 4 — Frontend + E2E
**Updated:** 2026-03-25

## Current

Phase 4 tasks generated. Ready to start task 1.

## Next Steps

- Task 1: Squad events in perception pipeline — fix 4 breaks so squad events reach the player via WebSocket
- Task 2: Frontend squad event rendering — add event types and colors to EventLog
- Task 3: E2E squad lifecycle — Playwright test covering movement, materialization, combat events

## Completed

- Phase 1 (Data Foundation) ✓ — MonsterTemplate, EncounterTable, FactionRelation, Squad models, YAML loading
- Phase 2 (Generalize Encounters + Hostile AI) ✓ — Encounter triggers for any active creature, faction-aware hostile AI in RuleBrain, abstract squad combat formula
- Phase 3 (Squad Movement + Materialization) ✓ — EcologyLayer skeleton, squad ownership migration, tick-based squad movement (patrol/roam/guard), squad-vs-squad combat, materialization when squad meets active character, dematerialization on departure, save/load with squad state
