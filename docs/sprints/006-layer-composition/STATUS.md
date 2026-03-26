# Sprint 006 Status

**Sprint:** 006-layer-composition
**Phase:** 3 — World Assembly Backend
**Updated:** 2026-03-26

## Current

Phase 3 tasks generated. Ready to start task 1.

## Next Steps

- Task 1: Library Catalog Service + API — scan library templates, compatibility filtering, REST endpoints
- Task 2: World Assembly + Fork API — assemble world from templates, fork template to custom, remove old content_saver

## Decisions

- All 5 layers (including entities) go to library — users fork complete worlds and tweak NPCs
- Settlements extracted from regions.yaml into standalone settlements.yaml (1 template = 1 layer)
- Delete arena, village, sneak_test — replace with test_vale (2 regions, all mechanics covered)
- Compatibility is declared explicitly via `requires_geography` in metadata.yaml — no runtime ID scanning
- Old create_world/update_world/content_saver flow replaced by assemble + fork
