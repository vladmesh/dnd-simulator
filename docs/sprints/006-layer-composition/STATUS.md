# Sprint 006 Status

**Sprint:** 006-layer-composition
**Phase:** 2 — Content Loader Reads from Manifest
**Updated:** 2026-03-26

## Current

Phase 2 tasks generated. Ready to start task 1.

## Next Steps

- Task 1: Manifest resolver + standalone settlements loader — new `resolve_manifest()` function and `load_settlements` refactor for standalone format
- Task 2: Wire manifest into GameService + remove old format — refactor start_game/get_world_template/list_worlds, delete sword_vale flat files

## Decisions

- All 5 layers (including entities) go to library — users fork complete worlds and tweak NPCs
- Settlements extracted from regions.yaml into standalone settlements.yaml (1 template = 1 layer)
- Delete arena, village, sneak_test — replace with test_vale (2 regions, all mechanics covered)
