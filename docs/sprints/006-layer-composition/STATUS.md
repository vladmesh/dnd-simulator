# Sprint 006 Status

**Sprint:** 006-layer-composition
**Phase:** 2 — Content Loader Reads from Manifest
**Updated:** 2026-03-26

## Current

Phase 2, Task 1: Manifest Resolver + Standalone Settlements Loader — done. Manifest resolver, standalone settlements loader, and GameService wiring all complete.

## Next Steps

- Task 2: Wire Manifest into GameService + Remove Old Format — delete sword_vale flat files, clean up dead code (load_world_meta, world.yaml), update remaining tests

## Decisions

- All 5 layers (including entities) go to library — users fork complete worlds and tweak NPCs
- Settlements extracted from regions.yaml into standalone settlements.yaml (1 template = 1 layer)
- Delete arena, village, sneak_test — replace with test_vale (2 regions, all mechanics covered)
