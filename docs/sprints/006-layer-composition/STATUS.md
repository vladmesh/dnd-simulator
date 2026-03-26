# Sprint 006 Status

**Sprint:** 006-layer-composition
**Phase:** 2 — Content Loader Reads from Manifest
**Updated:** 2026-03-26

## Current

Phase 2, Task 2: Wire Manifest into GameService + Remove Old Format — done. Old flat files deleted, dead code removed, 16 integration tests added.

## Next Steps

All Phase 2 tasks done.

## Decisions

- All 5 layers (including entities) go to library — users fork complete worlds and tweak NPCs
- Settlements extracted from regions.yaml into standalone settlements.yaml (1 template = 1 layer)
- Delete arena, village, sneak_test — replace with test_vale (2 regions, all mechanics covered)
