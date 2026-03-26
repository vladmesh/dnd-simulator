# Sprint 006 Status

**Sprint:** 006-layer-composition
**Phase:** 2 — Content Loader Reads from Manifest (COMPLETE)
**Updated:** 2026-03-26

## Current

Phase 2 complete. Manifest resolver, standalone settlements loader, GameService wiring, old format removal, integration test migration all done. E2E passed — both sword_vale (library) and test_vale (custom) load and play correctly.

Ready for Phase 3 task generation.

## Decisions

- All 5 layers (including entities) go to library — users fork complete worlds and tweak NPCs
- Settlements extracted from regions.yaml into standalone settlements.yaml (1 template = 1 layer)
- Delete arena, village, sneak_test — replace with test_vale (2 regions, all mechanics covered)
