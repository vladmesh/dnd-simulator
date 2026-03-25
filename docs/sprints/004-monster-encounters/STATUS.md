# Sprint 004 Status

**Sprint:** 004-monster-encounters → 004-living-world (replanned)
**Phase:** 3 — Squad Movement + Materialization (COMPLETE)
**Updated:** 2026-03-25

## Current

Phase 3 complete. EcologyLayer with tick-based squad movement, squad-vs-squad abstract combat, and materialization/dematerialization all implemented and tested. Integration tests green (36 total, 3 new squad tests). E2E green — no blockers. Ready for Phase 4 task generation.

## Completed

- Phase 1 (Data Foundation) ✓ — MonsterTemplate, EncounterTable, FactionRelation, Squad models, YAML loading
- Phase 2 (Generalize Encounters + Hostile AI) ✓ — Encounter triggers for any active creature, faction-aware hostile AI in RuleBrain, abstract squad combat formula
- Phase 3 (Squad Movement + Materialization) ✓ — EcologyLayer skeleton, squad ownership migration, tick-based squad movement (patrol/roam/guard), squad-vs-squad combat, materialization when squad meets active character, dematerialization on departure, save/load with squad state
